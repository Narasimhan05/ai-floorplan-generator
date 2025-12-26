import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import google.generativeai as genai
import os
import json
import io

# ==========================================
# 1. PAGE CONFIGURATION & VISIBILITY CSS
# ==========================================
st.set_page_config(layout="wide", page_title="ArchGenius AI - Floor Plan Generator")
st.markdown(
    """
    <style>
    .stApp { background-color: #FFFFFF; }
    h1, h2, h3 { color: #FF4B4B !important; }
    
    /* Metric Visibility Fixes */
    div[data-testid="stMetricValue"] {
        color: #006400 !important; 
        font-weight: 800;
        font-size: 2.5rem;
    }
    div[data-testid="stMetricLabel"] {
        color: #003366 !important;
        font-size: 1.1rem;
        font-weight: 600;
    }
    .stCaption {
        color: #333333 !important;
        font-style: italic;
    }
    
    .stButton>button {
        background-color: #FF4B4B;
        color: white;
        font-weight: bold;
        border-radius: 8px;
        height: 3em;
        width: 100%;
    }
    </style>
    """, 
    unsafe_allow_html=True
)

# ==========================================
# 2. FEASIBILITY ENGINE (Indian Context)
# ==========================================
def calculate_cost_and_compliance(data):
    results = {
        'cost_estimate': 0,
        'compliance_warnings': [],
        'total_area_sqft': 0,
        'bedroom_count': 0
    }
    
    EXTERIOR_WALL_COST = 3000  # ₹ per running foot
    INTERIOR_WALL_COST = 1200  # ₹ per running foot
    FLOORING_COST = 1500       # ₹ per sq ft
    
    total_ext_len = 0
    total_int_len = 0
    total_area = 0

    try:
        L = data['dimensions']['length']
        B = data['dimensions']['breadth']
        total_ext_len = 2 * (L + B)
        total_area = L * B
        results['total_area_sqft'] = total_area
    except KeyError:
        results['compliance_warnings'].append("CRITICAL: Missing dimension data.")
        return results

    for item in data.get('rooms', []):
        try:
            w = item.get('width', 0)
            h = item.get('height', 0)
            
            if item.get('type') not in ['door', 'window']:
                total_int_len += (2 * (w + h))

            if item.get('type') == 'bedroom':
                results['bedroom_count'] += 1
                if w < 7 or h < 7:
                    results['compliance_warnings'].append(
                        f"⚠️ **Warning:** '{item['name']}' is very narrow (< 7ft)."
                    )
        except Exception:
            pass

    est_cost = (total_ext_len * EXTERIOR_WALL_COST) + \
               ((total_int_len / 2) * INTERIOR_WALL_COST) + \
               (total_area * FLOORING_COST)
               
    results['cost_estimate'] = int(est_cost)
    return results

# ==========================================
# 3. RENDERING ENGINE (With Furniture)
# ==========================================
def render_floor_plan(data):
    """
    Draws the JSON data with Walls, Doors, and Furniture.
    """
    scale = 30  # Pixels per foot
    wall_thickness = 0.8 * scale 
    buffer = int(wall_thickness * 2)
    
    try:
        L = data['dimensions']['length']
        B = data['dimensions']['breadth']
        w_px = int(L * scale + (buffer * 2))
        h_px = int(B * scale + (buffer * 2))
    except:
        return None

    img = Image.new('RGB', (w_px, h_px), 'white')
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype("arial.ttf", 12)
        font_bold = ImageFont.truetype("arialbd.ttf", 14)
    except:
        font = ImageFont.load_default()
        font_bold = ImageFont.load_default()

    # 1. Draw Structure (Black Background for Walls)
    draw.rectangle(
        [buffer, buffer, w_px - buffer, h_px - buffer], 
        outline='black', width=int(wall_thickness)
    )

    colors = {
        'living_room': '#F0F8FF', 'kitchen': '#FFFACD', 'bedroom': '#FFF0F5',
        'bathroom': '#E0FFFF', 'corridor': '#F5F5F5', 'default': '#FFFFFF'
    }

    # 2. Draw Rooms (Floor)
    rooms = [r for r in data.get('rooms', []) if r.get('type') not in ['door', 'window']]
    
    for r in rooms:
        try:
            x1 = int(r['x'] * scale) + buffer
            y1 = int(r['y'] * scale) + buffer
            x2 = x1 + int(r['width'] * scale)
            y2 = y1 + int(r['height'] * scale)
            
            fill_c = colors.get(r.get('type', 'default'), colors['default'])
            draw.rectangle([x1, y1, x2, y2], fill=fill_c, outline='black', width=2)
            
            # Draw Labels
            if 'name' in r:
                draw.text((x1 + 5, y1 + 5), r['name'], fill='black', font=font_bold)
                draw.text((x1 + 5, y1 + 20), f"{r['width']}x{r['height']}", fill='#555', font=font)
        except:
            pass

    # 3. Draw Furniture (NEW!)
    # Simple symbolic drawing logic
    for f in data.get('furniture', []):
        try:
            fx = int(f['x'] * scale) + buffer
            fy = int(f['y'] * scale) + buffer
            fw = int(f['width'] * scale)
            fh = int(f['height'] * scale)
            ftype = f.get('type', 'default')
            
            # Base Furniture Shape (Grey/Brown)
            draw.rectangle([fx, fy, fx+fw, fy+fh], outline='#555555', fill='#D3D3D3', width=1)
            
            # Detail by type
            if ftype == 'bed':
                # Draw "Pillow" line
                pillow_h = int(fh * 0.2)
                draw.rectangle([fx, fy, fx+fw, fy+pillow_h], fill='white', outline='#555')
            elif ftype == 'sofa':
                # Draw "Backrest"
                back_h = int(fh * 0.25)
                draw.rectangle([fx, fy, fx+fw, fy+back_h], fill='#A9A9A9', outline=None)
            elif ftype == 'table':
                # Draw "Center"
                draw.rectangle([fx+5, fy+5, fx+fw-5, fy+fh-5], outline='#555', width=1)
            elif ftype == 'toilet':
                # Oval hint (circle)
                draw.ellipse([fx, fy, fx+fw, fy+fh], outline='black', width=1)
            
            # Label Furniture (Small text)
            if fw > 20 and fh > 10:
                draw.text((fx + 2, fy + fh/2 - 5), ftype, fill='#333', font=font)

        except Exception as e:
            pass

    # 4. Draw Doors & Windows (Top Layer - Cuts Walls)
    features = [r for r in data.get('rooms', []) if r.get('type') in ['door', 'window']]
    for f in features:
        try:
            x1 = int(f['x'] * scale) + buffer
            y1 = int(f['y'] * scale) + buffer
            x2 = x1 + int(f['width'] * scale)
            y2 = y1 + int(f['height'] * scale)
            
            if f['type'] == 'door':
                draw.rectangle([x1, y1, x2, y2], fill='white', outline=None) # Cut wall
                draw.rectangle([x1, y1, x2, y2], fill=None, outline='brown', width=2) # Frame
                # Draw swing arc (simplified as a line for now)
                draw.line([x1, y1, x2, y2], fill='brown', width=3)
            elif f['type'] == 'window':
                draw.rectangle([x1, y1, x2, y2], fill='#E0FFFF', outline='black', width=1)
        except:
            pass

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf

# ==========================================
# 4. AI REASONING ENGINE (The Brain)
# ==========================================
with st.sidebar:
    st.header("Configuration")
    env_key = os.environ.get("GEMINI_API_KEY")
    api_key_input = st.text_input("Gemini API Key", value=env_key if env_key else "", type="password")
    if api_key_input:
        genai.configure(api_key=api_key_input)
    st.info("Get your key from Google AI Studio.")

def get_floor_plan_from_ai(prompt):
    if not api_key_input:
        st.error("Please enter your API Key in the sidebar.")
        return None

    model = genai.GenerativeModel('gemini-2.5-flash')
    generation_config = genai.GenerationConfig(
        response_mime_type="application/json",
        temperature=1.0,  # Lower temperature is faster/more stable
        max_output_tokens=1500 # Limit output to prevent "rambling"
    )
    
    # --- PROMPT WITH FURNITURE INSTRUCTIONS ---
    system_instruction = """
    You are an expert architect. Generate a JSON blueprint for a 2D floor plan.
    
    MANDATORY RULES:

    1. DIMENSIONS: Use EXACT total dimensions requested (e.g., 60x20).

    2. TOTAL FILL: Sum of rooms MUST fill the boundary. No empty voids.

    3. LOGIC: 
       - Long/Narrow house? Add a 'Corridor' (4ft wide) to connect rooms.
       - Missing Bathroom? Add one automatically.
       - Missing Doors? Add doors to connect rooms to corridors/living areas.

    4. DATA STRUCTURE:
       - 'x' and 'y' are coordinates in feet from top-left (0,0).
       - Ensure rooms do not overlap.

    5. FURNITURE (NEW!):
       - Inside the 'furniture' list, add basic items for each room.
       - Living Room: 'sofa', 'table'
       - Bedroom: 'bed'
       - Kitchen: 'table' (island) or 'sink'
       - Bathroom: 'toilet', 'sink'
       - Ensure furniture coordinates are INSIDE their respective rooms.
    
    JSON FORMAT:
    {
      "dimensions": {"length": 60, "breadth": 20},
      "rooms": [
        {"name": "Living", "type": "living_room", "x": 0, "y": 0, "width": 20, "height": 20},
        {"name": "Corridor", "type": "corridor", "x": 20, "y": 0, "width": 40, "height": 4},
        {"name": "Bedroom", "type": "bedroom", "x": 20, "y": 4, "width": 15, "height": 16},
        {"name": "Door", "type": "door", "x": 20, "y": 10, "width": 0.5, "height": 3}
      ],
      "furniture": [
        {"type": "sofa", "x": 2, "y": 2, "width": 6, "height": 3},
        {"type": "bed", "x": 25, "y": 5, "width": 6, "height": 7},
        {"type": "toilet", "x": 55, "y": 2, "width": 2, "height": 2}
      ]
    }

    6. DOOR PLACEMENT RULE: 
   - A door MUST overlap a wall exactly. 
   - For a horizontal wall: set height to 0.8 and width to 3. 
   - For a vertical wall: set width to 0.8 and height to 3.
   - The 'x' and 'y' of the door MUST be exactly the same as the boundary of the room it belongs to.
    """
    
    try:
        response = model.generate_content(system_instruction + "\nUser Request: " + prompt)
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
    except Exception as e:
        st.error(f"AI Generation Error: {e}")
        return None

# ==========================================
# 5. MAIN APP UI
# ==========================================

st.title("🏠 ArchGenius AI")
st.subheader("AI-Powered Floor Plan Generator")
st.markdown("Generates professional floor plans with **Furniture**, **Cost (₹)** and **Compliance Checks**.")

prompt = st.text_area(
    "Describe your requirement:", 
    height=100, 
    value="Design a 30x50 feet office space. It should have a Reception area, one Conference Room, two private Cabins, and a general workspace."
)

if st.button("Generate Blueprint", type="primary"):
    
    with st.spinner("👷‍♂️ AI is drafting the blueprint..."):
        blueprint_data = get_floor_plan_from_ai(prompt)
        
        if blueprint_data:
            feasibility = calculate_cost_and_compliance(blueprint_data)
            img_data = render_floor_plan(blueprint_data)
            
            st.success("Generation Complete!")
            
            tab1, tab2, tab3 = st.tabs(["📐 Visual Plan", "💰 Feasibility Report", "💾 Raw Data"])
            
            with tab1:
                st.image(img_data, use_column_width=True)
                st.download_button("Download Image", img_data, "plan.png", "image/png")
            
            with tab2:
                st.header("Project Feasibility")
                st.markdown("---")
                st.metric(
                    label=f"Estimated Cost ({feasibility['total_area_sqft']} sq ft)",
                    value=f"₹{feasibility['cost_estimate']:,}"
                )
                st.caption("*Estimate based on Indian construction rates.*")
                
                st.markdown("### 📋 Design Checks")
                if feasibility['compliance_warnings']:
                    for warn in feasibility['compliance_warnings']:
                        st.error(warn)
                else:
                    st.success("✅ Layout generation successful within provided constraints.")
            
            with tab3:
                st.json(blueprint_data)
                st.download_button("Download JSON", json.dumps(blueprint_data, indent=2), "blueprint.json")
