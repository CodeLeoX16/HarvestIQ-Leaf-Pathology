import os
import io
import json
import time
import hashlib
from contextlib import asynccontextmanager
import torch
from PIL import Image
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from transformers import AutoImageProcessor, AutoModelForImageClassification
from google import genai

load_dotenv()

# Limit PyTorch CPU threads to avoid resource contention on free tier hosts
torch.set_num_threads(2)

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
MODEL_ID = "wambugu71/crop_leaf_diseases_vit"

# ---------------------------------------------------------
# 1. Global Model and Processor Initialization
# ---------------------------------------------------------
processor = None
model = None

try:
    processor = AutoImageProcessor.from_pretrained(MODEL_ID)
    model = AutoModelForImageClassification.from_pretrained(MODEL_ID)
    if os.path.exists("model.pth"):
        model.load_state_dict(torch.load("model.pth", map_location=DEVICE))
        print("✓ Local PyTorch weights verified.")
    model.to(DEVICE)
    model.eval()
except Exception as e:
    print(f"Notice: Running fallback mode for local model: {e}")

# ---------------------------------------------------------
# 2. Multi-Key API Rotation & Gemini Client Setup
# ---------------------------------------------------------
raw_keys = os.getenv("GEMINI_API_KEY", "")
api_keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
current_key_idx = 0
GEMINI_MODEL = "gemini-2.5-flash"

def get_gemini_client():
    global current_key_idx
    if not api_keys:
        return None
    return genai.Client(api_key=api_keys[current_key_idx])

def rotate_key():
    global current_key_idx
    if len(api_keys) > 1:
        current_key_idx = (current_key_idx + 1) % len(api_keys)
        print(f"⚠️ Quota threshold reached. Switched to API key #{current_key_idx + 1}")

if api_keys:
    print(f"✓ Gemini API connected with {len(api_keys)} key(s) in active rotation pool.")
else:
    print("⚠️ WARNING: GEMINI_API_KEY is not set. Out-of-domain plant diagnoses may fail.")

# ---------------------------------------------------------
# 3. Quota Optimization: Hash Caching & Image Downscaling
# ---------------------------------------------------------
DIAGNOSIS_CACHE = {}

def get_image_hash(image_bytes: bytes) -> str:
    return hashlib.sha256(image_bytes).hexdigest()

def compress_image_for_api(image_bytes: bytes, max_dim: int = 768) -> bytes:
    """Downscales images to keep token consumption minimal under free quotas."""
    try:
        im = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        im.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=82)
        return buf.getvalue()
    except Exception:
        return image_bytes

# ---------------------------------------------------------
# 4. Lifespan Manager (Warmup at Boot)
# ---------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm local model with a dummy inference to eliminate cold latency
    if model and processor:
        try:
            dummy = Image.new("RGB", (224, 224), color="green")
            inputs = processor(images=dummy, return_tensors="pt").to(DEVICE)
            with torch.no_grad():
                model(**inputs)
            print("✓ Local model warmed up in memory.")
        except Exception as err:
            print(f"Warmup warning: {err}")
    yield

app = FastAPI(title="HarvestIQ Leaf Disease Engine", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# 5. Health Check Endpoint (Background Wake-Up)
# ---------------------------------------------------------
@app.get("/api/health")
async def health_check():
    return {
        "status": "online",
        "engine": "HarvestIQ AI",
        "device": str(DEVICE),
        "keysConfigured": len(api_keys)
    }

# ---------------------------------------------------------
# 6. Universal Gemini Diagnostician (With Retry & Backoff)
# ---------------------------------------------------------
def diagnose_with_gemini(image_bytes: bytes, mime_type: str = "image/jpeg", max_retries: int = 3):
    img_hash = get_image_hash(image_bytes)
    if img_hash in DIAGNOSIS_CACHE:
        print("✓ Zero-quota hit: Served diagnosis from in-memory cache.")
        return DIAGNOSIS_CACHE[img_hash]

    compressed_bytes = compress_image_for_api(image_bytes)

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
    for attempt in range(max_retries):
        client = get_gemini_client()
        if not client:
            return None

        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[
                    {
                        "role": "user",
                        "parts": [
                            {"text": prompt},
                            {
                                "inline_data": {
                                    "mime_type": "image/jpeg",
                                    "data": compressed_bytes
                                }
                            }
                        ]
                    }
                ],
                config={"response_mime_type": "application/json"}
            )
            result = json.loads(response.text)
            DIAGNOSIS_CACHE[img_hash] = result
            return result

        except Exception as err:
            err_str = str(err).lower()
            if "429" in err_str or "resource_exhausted" in err_str or "quota" in err_str:
                print(f"Rate limit on attempt {attempt + 1}. Rotating key & backing off...")
                rotate_key()
                time.sleep(2 ** (attempt + 1))
            else:
                print(f"Gemini Diagnostics API error: {err}")
                break

    return None

# ---------------------------------------------------------
# 7. Local Prediction Agronomic Enrichment
# ---------------------------------------------------------
def enrich_local_prediction(plant: str, disease: str, is_healthy: bool):
    if is_healthy:
        return {
            "symptoms": ["Leaf tissue exhibits normal turgor, uniform chlorophyll distribution, and healthy blade margins."],
            "causes": ["Adequate light intensity, balanced soil hydration, and optimal nutrition."],
            "treatments": ["Continue standard irrigation and balanced seasonal N-P-K feeding cycles."],
            "organicRemedies": ["Apply compost tea or foliar sea-kelp spray as an organic growth enhancer."],
            "preventions": ["Routinely inspect foliage for pest introduction and keep tree basins weed-free."]
        }

    client = get_gemini_client()
    if client:
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
            res = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config={"response_mime_type": "application/json"}
            )
            return json.loads(res.text)
        except Exception:
            rotate_key()

    return {
        "symptoms": ["Visible lesions, necrotic leaf spots, or chlorotic foliage margins."],
        "causes": ["Fungal spore incubation accelerated by moisture and leaf humidity."],
        "treatments": ["Prune affected branches. Apply registered copper hydroxide or systemic fungicide."],
        "organicRemedies": ["Spray cold-pressed emulsified neem oil (0.5%) or potassium bicarbonate."],
        "preventions": ["Transition to drip irrigation; maintain canopy spacing for optimal air circulation."]
    }

# ---------------------------------------------------------
# 8. Treatment Guide Translation Endpoint
# ---------------------------------------------------------
class TreatmentGuideRequest(BaseModel):
    diagnosis: dict
    language: str = "English"

SUPPORTED_GUIDE_LANGUAGES = {
    "English", "Hindi", "Telugu", "Tamil", "Kannada", "Marathi", "Bengali"
}

@app.post("/api/treatment-guide")
async def create_treatment_guide(request: TreatmentGuideRequest):
    if request.language not in SUPPORTED_GUIDE_LANGUAGES:
        raise HTTPException(status_code=400, detail="Unsupported guide language.")

    diagnosis = request.diagnosis
    required_fields = ("plantName", "conditionName", "treatments", "organicRemedies", "preventions")
    if any(field not in diagnosis for field in required_fields):
        raise HTTPException(status_code=400, detail="Incomplete diagnosis data.")

    if request.language == "English":
        return JSONResponse({"language": "English", "diagnosis": diagnosis})

    client = get_gemini_client()
    if not client:
        raise HTTPException(
            status_code=503,
            detail="Gemini translation is unavailable. Configure GEMINI_API_KEY and try again."
        )

    prompt = f"""
Translate the following plant disease treatment guide into {request.language}.
Keep the JSON keys and array structure exactly the same. Translate all human-readable
values, but preserve numbers, percentages, scientific names, and product names where
appropriate. Do not add medical claims or invent treatments. Return only valid JSON.

{json.dumps(diagnosis, ensure_ascii=False)}
"""
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )
        translated = json.loads(response.text)
        return JSONResponse({"language": request.language, "diagnosis": translated})
    except (json.JSONDecodeError, ValueError) as err:
        print(f"Treatment guide translation response error: {err}")
        raise HTTPException(status_code=502, detail="Gemini returned an invalid guide format.")
    except Exception as err:
        print(f"Treatment guide translation error: {err}")
        rotate_key()
        raise HTTPException(status_code=502, detail="Treatment guide translation failed due to rate limits.")

# ---------------------------------------------------------
# 9. Main Foliage Diagnostic Endpoint
# ---------------------------------------------------------
@app.post("/api/diagnose")
async def diagnose_leaf(leafImage: UploadFile = File(...)):
    if not leafImage.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="The uploaded file is not a valid image.")

    image_bytes = await leafImage.read()

    local_predicted_invalid = False
    local_result = None

    # Step A: Local Model Inference First
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

            # If the specimen falls outside the local crop domain
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

    # Step B: Universal Fallback via Gemini (for any tree/crop outside the local model)
    if local_predicted_invalid or not local_result:
        print("Routing specimen to Universal Tree & Plant Diagnostician...")
        gemini_result = diagnose_with_gemini(image_bytes, leafImage.content_type)
        if gemini_result:
            return JSONResponse(gemini_result)

    # Step C: Return local result if valid
    if local_result:
        return JSONResponse(local_result)

    # Step D: Graceful fallback when completely rate limited or offline
    return JSONResponse({
        "plantName": "Specimen Quota Cooldown",
        "conditionName": "Temporary Rate Limit",
        "healthStatus": "Inconclusive",
        "pathogenType": "None",
        "confidenceScore": 0.0,
        "severityRating": "None",
        "symptoms": ["The free API quota was temporarily exhausted for new tree specimens."],
        "causes": ["High request burst within the 60-second window."],
        "treatments": ["Wait 30-45 seconds before submitting the next leaf scan."],
        "organicRemedies": ["Add a secondary free API key to .env (comma-separated) to multiply capacity."],
        "preventions": ["Test with identical leaves to leverage zero-quota local caching."]
    })

# Serve static frontend files from 'public' directory
app.mount("/", StaticFiles(directory="public", html=True), name="public")

# ---------------------------------------------------------
# 10. Execution Entrypoint for Local & Cloud Deployments
# ---------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    # reload=False is required on Render to stay within 512 MB memory limit
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
