import os
import io
import json
import base64
import torch
from PIL import Image
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from transformers import AutoImageProcessor, AutoModelForImageClassification
from google import genai

load_dotenv()

app = FastAPI(title="HarvestIQ Leaf Disease Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
MODEL_ID = "wambugu71/crop_leaf_diseases_vit"

print(f"Loading HarvestIQ AI Vision Engine on device: {DEVICE}...")

# 1. Initialize Local Model and Processor
processor = None
model = None

try:
    processor = AutoImageProcessor.from_pretrained(MODEL_ID)
    model = AutoModelForImageClassification.from_pretrained(MODEL_ID)
    if os.path.exists("model.pth"):
        model.load_state_dict(torch.load("model.pth", map_location=DEVICE))
        print("✓ Local model weights loaded successfully.")
    model.to(DEVICE)
    model.eval()
except Exception as e:
    print(f"Notice: Running with fallback mode: {e}")

# 2. Initialize Gemini API Client
gemini_key = os.getenv("GEMINI_API_KEY")
ai_client = genai.Client(api_key=gemini_key) if gemini_key else None

if ai_client:
    print("✓ Gemini Universal Plant Pathology API connected.")
else:
    print("⚠️ WARNING: GEMINI_API_KEY is not set. Tree diagnoses outside the 13 local classes may fail.")

# Universal Gemini Fallback Diagnostician for ANY tree or plant species
def diagnose_with_gemini(image_bytes: bytes, mime_type: str = "image/jpeg"):
    if not ai_client:
        return None

    prompt = """
You are an expert plant pathologist and botanist.
Analyze this leaf image from any tree, agricultural crop, fruit, or plant.
Identify the host plant and diagnose any pathology, pests, deficiency, or if it is healthy.

Return ONLY a raw JSON object with this exact structure:
{
  "plantName": "Common plant/tree name (e.g. Apple, Mango, Tomato, Teak, Neem, Rose)",
  "conditionName": "Specific disease or status (e.g. Apple Scab, Powdery Mildew, Healthy Foliage)",
  "healthStatus": "Healthy" or "Infected",
  "pathogenType": "Fungal" or "Bacterial" or "Viral" or "Pest" or "Nutritional" or "None",
  "confidenceScore": 95.0,
  "severityRating": "None" or "Mild" or "Moderate" or "Severe",
  "symptoms": ["Detailed visual symptom 1", "Detailed visual symptom 2", "Detailed visual symptom 3"],
  "causes": ["Pathogen name or abiotic root cause 1", "Cause 2"],
  "treatments": ["Immediate chemical/physical action 1", "Action 2", "Action 3"],
  "organicRemedies": ["Organic/eco-friendly remedy 1", "Remedy 2"],
  "preventions": ["Long-term prevention protocol 1", "Protocol 2", "Protocol 3"]
}
"""
    try:
        response = ai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": image_bytes
                            }
                        }
                    ]
                }
            ],
            config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text)
    except Exception as err:
        print(f"Gemini Universal Diagnostics Error: {err}")
        return None

# Local enrichment helper
def enrich_local_prediction(plant: str, disease: str, is_healthy: bool):
    if is_healthy:
        return {
            "symptoms": ["Leaf tissue exhibits normal turgor, uniform chlorophyll distribution, and healthy blade margins."],
            "causes": ["Adequate light intensity, balanced soil hydration, and optimal nutrition."],
            "treatments": ["Continue standard irrigation and balanced seasonal N-P-K feeding cycles."],
            "organicRemedies": ["Apply compost tea or foliar sea-kelp spray as an organic growth enhancer."],
            "preventions": ["Routinely inspect foliage for pest introduction and keep tree basins weed-free."]
        }
    
    if ai_client:
        try:
            prompt = f"""
As an agronomist, provide a treatment prescription for {plant} diagnosed with {disease}.
Strictly output JSON with these keys:
{{
  "symptoms": ["3 bullet items"],
  "causes": ["2 root causes"],
  "treatments": ["3 actionable treatments"],
  "organicRemedies": ["2 organic cures"],
  "preventions": ["3 preventive steps"]
}}
"""
            res = ai_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={"response_mime_type": "application/json"}
            )
            return json.loads(res.text)
        except Exception:
            pass

    # Generic Fallback
    return {
        "symptoms": ["Visible lesions, necrotic leaf spots, or chlorotic foliage margins."],
        "causes": ["Fungal spore incubation accelerated by moisture and leaf humidity."],
        "treatments": ["Prune affected branches. Apply registered copper hydroxide or systemic fungicide."],
        "organicRemedies": ["Spray cold-pressed emulsified neem oil (0.5%) or potassium bicarbonate."],
        "preventions": ["Transition to drip irrigation; maintain canopy spacing for optimal air circulation."]
    }

@app.post("/api/diagnose")
async def diagnose_leaf(leafImage: UploadFile = File(...)):
    if not leafImage.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="The uploaded file is not a valid image.")

    image_bytes = await leafImage.read()
    
    # 1. Try Local Model Inference
    local_predicted_invalid = False
    local_result = None

    if model and processor:
        try:
            pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            inputs = processor(images=pil_image, return_tensors="pt").to(DEVICE)

            with torch.no_grad():
                outputs = model(**inputs)
                probs = torch.nn.functional.softmax(outputs.logits[0], dim=0)
                confidence, predicted_idx = torch.max(probs, 0)

            raw_label = model.config.id2label[predicted_idx.item()]
            conf_percentage = round(confidence.item() * 100, 1)

            if raw_label.strip().lower() == "invalid" or conf_percentage < 65.0:
                local_predicted_invalid = True
            else:
                parts = raw_label.split("___")
                plant_name = parts[0].replace("_", " ").title()
                disease_name = parts[1].replace("_", " ").title() if len(parts) > 1 else "Healthy"
                is_healthy = "healthy" in disease_name.lower()
                
                enriched = enrich_local_prediction(plant_name, disease_name, is_healthy)
                
                local_result = {
                    "plantName": plant_name,
                    "conditionName": disease_name,
                    "healthStatus": "Healthy" if is_healthy else "Infected",
                    "pathogenType": "None" if is_healthy else "Fungal/Bacterial",
                    "confidenceScore": conf_percentage,
                    "severityRating": "None" if is_healthy else ("Severe" if conf_percentage > 85 else "Moderate"),
                    "symptoms": enriched.get("symptoms", []),
                    "causes": enriched.get("causes", []),
                    "treatments": enriched.get("treatments", []),
                    "organicRemedies": enriched.get("organicRemedies", []),
                    "preventions": enriched.get("preventions", [])
                }
        except Exception as e:
            print("Local model inference error:", e)
            local_predicted_invalid = True

    # 2. Universal Tree & Crop Detection via Gemini
    if local_predicted_invalid or not local_result:
        print("Routing specimen to Universal Tree & Plant Diagnostician...")
        gemini_result = diagnose_with_gemini(image_bytes, leafImage.content_type)
        if gemini_result:
            return JSONResponse(gemini_result)

    # 3. If local succeeded, return it
    if local_result:
        return JSONResponse(local_result)

    # 4. Fallback if offline and non-indexed
    return JSONResponse({
        "plantName": "Unrecognized Tree / Specimen",
        "conditionName": "Specimen Out of Model Scope",
        "healthStatus": "Inconclusive",
        "pathogenType": "None",
        "confidenceScore": 0.0,
        "severityRating": "None",
        "symptoms": ["The uploaded specimen could not be classified by the local grain/crop model."],
        "causes": ["Offline mode active or unsupported tree foliage."],
        "treatments": ["Verify your GEMINI_API_KEY in .env to identify all wild tree species."],
        "organicRemedies": ["N/A"],
        "preventions": ["Ensure leaves are centered under clear natural lighting."]
    })

# Serve static frontend files
app.mount("/", StaticFiles(directory="public", html=True), name="public")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)