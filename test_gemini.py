import os
import PIL.Image
import PIL.ImageDraw
from google import genai
from dotenv import load_dotenv

# Load API key from .env file
load_dotenv()

# Initialize the Gemini client
client = genai.Client()

print("--- Starting Gemini API Validation ---")

# 1. Text-Only Validation
print("\n1. Testing Text-Only Prompt...")
try:
    text_prompt = "Explain smart budgeting for a party in one sentence."
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=text_prompt
    )
    print(f"Success! Response: {response.text}")
except Exception as e:
    print(f"Text validation failed: {e}")

# 2. Multimodal (Image + Text) Validation
print("\n2. Testing Multimodal (Image + Text) Prompt...")
try:
    sample_image_path = "sample_room_plan.jpg"
    
    # Generate a sample layout image locally if it doesn't exist
    if not os.path.exists(sample_image_path):
        print("Generating local sample image...")
        img_temp = PIL.Image.new('RGB', (400, 400), color=(240, 240, 240))
        draw = PIL.ImageDraw.Draw(img_temp)
        # Draw room outline
        draw.rectangle([50, 50, 350, 350], outline="black", width=4)
        draw.rectangle([60, 60, 190, 190], outline="blue", width=2)
        draw.rectangle([210, 60, 340, 190], outline="green", width=2)
        img_temp.save(sample_image_path)

    # Open local image and test multimodal endpoint
    img = PIL.Image.open(sample_image_path)
    multimodal_response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=["Analyze this room layout and describe what shapes or areas you see.", img]
    )
    print(f"Success! Response: {multimodal_response.text}")

except Exception as e:
    print(f"Multimodal validation failed: {e}")