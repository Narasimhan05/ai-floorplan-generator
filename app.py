import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import google.generativeai as genai
import os
import json
import io

# --- 1. Configure Gemini API ---
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    st.error("GEMINI_API_KEY environment variable not set. Please set it before running the app.")
    st.stop()

genai.configure(api_key=api_key)

# --- AI Core: Generate Floor Plan Data ---
@st.cache_data
def get_gemini_model():
    return genai.GenerativeModel('gemini-1.5-flash')

def generate_floor_plan_data(user_description):
    model = get_gemini_model()
    
    full_prompt = f"""
    You are an expert architectural designer.
    Based on the following user request, generate a simple 2D rectangular floor plan.
    The output must be a single JSON object.

    USER REQUEST: {user_description}

    Include the overall dimensions of the house (length and breadth) and a list of rooms.
    For each room, provide its name, its type (e.g., 'bedroom', 'living room', 'bathroom', 'kitchen', 'doorway'),
    and its position (x, y coordinates from top-left, in feet) and size (width, height, in feet).
    Ensure rooms do not overlap and fit within the overall house dimensions.
    Include doorways between rooms where logical, representing them as small rectangles.
    Ensure the layout is functional and aesthetically pleasing for a typical house.

    RESPONSE STRUCTURE EXAMPLE:
    {{
      "dimensions": {{"length": 60, "breadth": 20}},
      "rooms": [
        {{"name": "Living Room", "type": "living_room", "x": 0, "y": 0, "width": 25, "height": 20}},
        {{"name": "Kitchen", "type": "kitchen", "x": 25, "y": 0, "width": 15, "height": 20}},
        {{"name": "Bedroom 1", "type": "bedroom", "x": 0, "y": 20, "width": 20, "height": 10}},
        {{"name": "Bathroom 1", "type": "bathroom", "x": 20, "y": 20, "width": 10, "height": 10}},
        {{"name": "Doorway", "type": "door", "x": 24, "y": 0, "width": 2, "height": 1}}
      ]
    }}
    Please ensure the 'dimensions' in the JSON are consistent with the overall area or given dimensions in the user's request.
    """
    
    try:
        response = model.generate_content(full_prompt)
        json_string = response.text.strip().lstrip("```json").rstrip("```")
        floor_plan = json.loads(json_string)
        if 'dimensions' not in floor_plan or 'rooms' not in floor_plan:
            raise ValueError("Missing 'dimensions' or 'rooms' in AI response.")
        return floor_plan
    except json.JSONDecodeError as e:
        st.error(f"AI response was not valid JSON: {e}")
        return None
    except ValueError as e:
        st.error(f"AI response error: {e}")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        return None

# --- Rendering Engine: Convert Data to Image ---
def render_floor_plan(data):
    scale = 20
    try:
        img_width = data['dimensions']['length'] * scale
        img_height = data['dimensions']['breadth'] * scale
    except KeyError:
        return None
    
    image = Image.new('RGB', (img_width, img_height), 'white')
    draw = ImageDraw.Draw(image)
    try:
        font_size = max(10, int(scale * 0.7))
        font = ImageFont.truetype("arial.ttf", font_size)
    except IOError:
        font = ImageFont.load_default()
    draw.rectangle([0, 0, img_width, img_height], outline='black', width=3)
    room_colors = {
        'living_room': (255, 200, 200),
        'kitchen': (200, 255, 200),
        'bedroom': (200, 200, 255),
        'bathroom': (255, 255, 200),
        'door': (100, 50, 0),
        'hallway': (230, 230, 230),
        'default': (240, 240, 240)
    }
    for item in data.get('rooms', []):
        try:
            x, y, width, height = item['x'] * scale, item['y'] * scale, item['width'] * scale, item['height'] * scale
            color = room_colors.get(item.get('type', 'default'), room_colors['default'])
            if item.get('type') == 'door':
                draw.rectangle([x, y, x + width, y + height], fill=color, outline=color)
            else:
                draw.rectangle([x, y, x + width, y + height], fill=color, outline='black', width=1)
            if item.get('name') and item.get('type') != 'door':
                draw.text((x + 5, y + 5), item['name'], fill='black', font=font)
        except (KeyError, ValueError) as e:
            st.warning(f"Skipping malformed room data: {e} in {item}")
        except Exception as e:
            st.warning(f"Error drawing item: {e}")
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    return img_byte_arr

# --- Streamlit UI ---
st.set_page_config(layout="wide", page_title="AI Floor Plan Generator")

# Inject custom CSS for a more aesthetic look with a white and red theme
st.markdown(
    """
    <style>
    /* General font for the whole app */
    html, body, [class*="st-"] {
        font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
    }
    
    /* Background animation */
    body {
        background-color: #F8F8F8; /* Light gray background */
        overflow-x: hidden;
    }

    body::before {
        content: '';
        position: fixed;
        top: 0;
        left: 0;
        width: 200vw;
        height: 200vh;
        z-index: -1;
        background-image:
            linear-gradient(rgba(255, 75, 75, 0.1) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255, 75, 75, 0.1) 1px, transparent 1px);
        background-size: 50px 50px;
        animation: flow 120s linear infinite;
    }

    @keyframes flow {
        from {
            transform: translate(0, 0);
        }
        to {
            transform: translate(calc(50px * -2), calc(50px * -2));
        }
    }

    /* Set main app background to white */
    .stApp {
        background-color: #FFFFFF;
    }

    /* Center the title and use a bold red color */
    h1 {
        font-size: 3rem;
        color: #FF4B4B; /* Bold red color */
        text-align: left;
        letter-spacing: -1px;
        margin-bottom: 0.5rem;
    }
    
    /* Style the main header for better alignment */
    .header-container {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 1rem;
        padding: 1rem 0;
    }
    
    /* Add a subtle shadow and red border to the input container */
    .stContainer {
        background-color: #FFFFFF;
        border: 1px solid #FF4B4B; /* Red border */
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        padding: 20px;
        margin-bottom: 20px;
    }

    /* Style the main button */
    .stButton>button {
        background-color: #FF4B4B; /* Red button */
        color: white;
        font-weight: bold;
        border: none;
        border-radius: 8px;
        padding: 10px 24px;
        transition: transform 0.2s ease-in-out;
    }
    .stButton>button:hover {
        transform: scale(1.02);
    }
    
    /* Adjust text area label */
    .stTextArea > label {
        font-weight: bold;
        color: #262730; /* Dark text for contrast */
    }
    /* Adjust subheader text color */
    h2, h3, h4, h5, h6 {
        color: #262730;
    }

    </style>
    """, unsafe_allow_html=True
)

# Use columns for a better header layout with the logo
header_col1, header_col2 = st.columns([1, 4])
with header_col1:
    st.image("ai_floorplan_logo.png", width=120) 
with header_col2:
    st.markdown("<h1 style='text-align: left; color: #FF4B4B; margin-top: 0;'>AI-Powered Floor Plan Generator</h1>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: left; margin-top: -10px;'>Your personal architectural assistant powered by Gemini.</h4>", unsafe_allow_html=True)

st.markdown("---")

input_container = st.container(border=True)
with input_container:
    st.subheader("Design Your Home ✨")
    user_description = st.text_area(
        "Describe your dream house here:",
        "Generate a 1200 sq ft house, 60 feet long and 20 feet wide. It should have 3 bedrooms, 2 bathrooms, an open-concept living room, and a kitchen. Make the master bedroom have an ensuite bathroom.",
        height=150
    )

generate_button = st.button("Generate Floor Plan", use_container_width=True)

if generate_button:
    if user_description:
        with st.spinner('Thinking and drawing your floor plan...'):
            floor_plan_data = generate_floor_plan_data(user_description)
            
            if floor_plan_data:
                image_bytes = render_floor_plan(floor_plan_data)
                
                if image_bytes:
                    st.success("Floor plan successfully generated! 🎉")
                    st.image(image_bytes, caption="Your Generated Floor Plan", use_column_width=True)
                    st.download_button(
                        label="Download Floor Plan (PNG)",
                        data=image_bytes,
                        file_name="floor_plan.png",
                        mime="image/png"
                    )
                else:
                    st.error("Failed to render the floor plan image.")
            else:
                st.error("Could not generate floor plan data. Please try a different prompt or check the AI's response.")
    else:
        st.warning("Please enter a description for your house plan.")

st.markdown("---")
st.caption("Powered by Google Gemini and Streamlit")