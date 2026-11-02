
import os
import io
import json
import torch

from PIL import Image
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from transformers import (
    AutoImageProcessor,
    AutoModelForImageClassification
)

from google import genai


# =========================================================
# 1. ENVIRONMENT CONFIGURATION
# =========================================================

load_dotenv()

app = FastAPI(title="HarvestIQ Leaf Disease Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

MODEL_ID = "wambugu71/crop_leaf_diseases_vit"


# =========================================================
# 2. GEMINI API KEY ROTATION
# =========================================================

GEMINI_API_KEYS = [
    os.getenv("GEMINI_API_KEY_1"),
    os.getenv("GEMINI_API_KEY_2"),
    os.getenv("GEMINI_API_KEY_3")
]

# Remove missing or empty keys
GEMINI_API_KEYS = [
    key.strip()
    for key in GEMINI_API_KEYS
    if key and key.strip()
]

# Optional backward compatibility with the old variable
old_key = os.getenv("GEMINI_API_KEY")

if old_key and old_key.strip() and old_key.strip() not in GEMINI_API_KEYS:
    GEMINI_API_KEYS.append(old_key.strip())


def get_gemini_clients():
    clients = []

    for index, key in enumerate(GEMINI_API_KEYS, start=1):
        try:
            client = genai.Client(api_key=key)
            clients.append(client)

            print(f"Gemini API client {index} initialized.")

        except Exception as error:
            print(
                f"Gemini client {index} initialization failed:",
                repr(error)
            )

    return clients


gemini_clients = get_gemini_clients()


def generate_json_with_rotation(**kwargs):
    """
    Attempts Gemini requests using each configured API key.

    If one key fails, the next key is tried.
    Returns parsed JSON or None if every key fails.
    """

    if not gemini_clients:
        print("No Gemini API clients are configured.")
        return None

    for index, client in enumerate(gemini_clients, start=1):

        try:
            print(f"Trying Gemini API client {index}...")

            response = client.models.generate_content(**kwargs)

            if not response.text:
                raise ValueError("Gemini returned an empty response.")

            result = json.loads(response.text)

            if not isinstance(result, dict):
                raise ValueError("Gemini response is not a JSON object.")

            print(f"Gemini request successful using client {index}.")

            return result

        except Exception as error:

            print(
                f"Gemini API client {index} failed:",
                repr(error)
            )

            if index < len(gemini_clients):
                print("Trying the next Gemini API key...")

    print("All Gemini API keys failed.")

    return None


if gemini_clients:
    print(
        f"Gemini Universal Plant Pathology API connected. "
        f"{len(gemini_clients)} client(s) configured."
    )
else:
    print(
        "WARNING: No Gemini API keys configured. "
        "Universal plant diagnosis will be unavailable."
    )


# =========================================================
# 3. LOCAL MODEL INITIALIZATION
# =========================================================

print(f"Loading HarvestIQ AI Vision Engine on device: {DEVICE}...")

processor = None
model = None

try:
    processor = AutoImageProcessor.from_pretrained(MODEL_ID)

    model = AutoModelForImageClassification.from_pretrained(
        MODEL_ID
    )

    # Load optional model weights
    if os.path.exists("model.pth"):

        model.load_state_dict(
            torch.load(
                "model.pth",
                map_location=DEVICE
            )
        )

        print("Local model weights loaded successfully.")

    model.to(DEVICE)
    model.eval()

    print("Local vision model loaded successfully.")

except Exception as error:

    print("Local model initialization failed:", repr(error))

    processor = None
    model = None


# =========================================================
# 4. UNIVERSAL GEMINI PLANT DIAGNOSIS
# =========================================================

def diagnose_with_gemini(
    image_bytes: bytes,
    mime_type: str = "image/jpeg"
):

    prompt = """
You are an expert plant pathologist and botanist.

Analyze the uploaded leaf image from any tree, agricultural
crop, fruit, or plant.

Identify the host plant and diagnose any visible pathology,
pests, nutritional deficiencies, or healthy condition.

Important:
- Do not invent a disease if visual evidence is insufficient.
- Do not confuse healthy foliage with infected foliage.
- If the image is not a recognizable plant leaf, return
  an inconclusive result.
- Provide practical and scientifically responsible advice.
- Do not claim certainty based only on an unclear image.

Return ONLY a raw JSON object with this exact structure:

{
  "plantName": "Common plant/tree name",
  "conditionName": "Specific disease or health status",
  "healthStatus": "Healthy, Infected, or Inconclusive",
  "pathogenType": "Fungal, Bacterial, Viral, Pest, Nutritional, or None",
  "confidenceScore": 95.0,
  "severityRating": "None, Mild, Moderate, Severe, or None",
  "symptoms": [
    "Detailed visual symptom 1",
    "Detailed visual symptom 2",
    "Detailed visual symptom 3"
  ],
  "causes": [
    "Pathogen name or abiotic root cause 1",
    "Cause 2"
  ],
  "treatments": [
    "Immediate chemical or physical action 1",
    "Action 2",
    "Action 3"
  ],
  "organicRemedies": [
    "Organic or eco-friendly remedy 1",
    "Remedy 2"
  ],
  "preventions": [
    "Long-term prevention protocol 1",
    "Protocol 2",
    "Protocol 3"
  ]
}
"""

    result = generate_json_with_rotation(
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
        config={
            "response_mime_type": "application/json"
        }
    )

    return result


# =========================================================
# 5. LOCAL PREDICTION ENRICHMENT
# =========================================================

def enrich_local_prediction(
    plant: str,
    disease: str,
    is_healthy: bool
):

    if is_healthy:

        return {
            "symptoms": [
                "Leaf tissue exhibits normal turgor, "
                "uniform chlorophyll distribution, "
                "and healthy blade margins."
            ],

            "causes": [
                "Adequate light intensity, balanced soil "
                "hydration, and optimal nutrition."
            ],

            "treatments": [
                "Continue standard irrigation and balanced "
                "seasonal N-P-K feeding cycles."
            ],

            "organicRemedies": [
                "Apply compost tea or foliar sea-kelp spray "
                "as an organic growth enhancer."
            ],

            "preventions": [
                "Routinely inspect foliage for pest introduction "
                "and keep tree basins weed-free."
            ]
        }

    prompt = f"""
You are an expert agricultural scientist.

Provide a practical treatment prescription for:

Plant: {plant}
Detected condition: {disease}

Strictly return JSON with these keys:

{{
    "symptoms": ["3 visual symptoms"],
    "causes": ["2 possible root causes"],
    "treatments": ["3 actionable treatments"],
    "organicRemedies": ["2 organic remedies"],
    "preventions": ["3 preventive steps"]
}}

Give scientifically responsible advice.
Do not recommend unnecessary chemical applications.
"""

    result = generate_json_with_rotation(
        model="gemini-2.5-flash",
        contents=prompt,
        config={
            "response_mime_type": "application/json"
        }
    )

    if result:
        return result

    # Generic fallback if every Gemini key fails
    return {
        "symptoms": [
            "Visible lesions, necrotic leaf spots, "
            "or chlorotic foliage margins."
        ],

        "causes": [
            "Possible fungal infection or environmental stress."
        ],

        "treatments": [
            "Remove severely affected leaves.",
            "Improve airflow around the plant.",
            "Use an appropriate registered treatment "
            "after confirming the disease."
        ],

        "organicRemedies": [
            "Use an appropriate organic treatment "
            "after identifying the cause."
        ],

        "preventions": [
            "Avoid excessive leaf wetness.",
            "Maintain proper spacing and airflow.",
            "Inspect plants regularly for early symptoms."
        ]
    }


# =========================================================
# 6. DIAGNOSIS API
# =========================================================

@app.post("/api/diagnose")
async def diagnose_leaf(
    leafImage: UploadFile = File(...)
):

    # Validate uploaded file
    if not leafImage.content_type or not leafImage.content_type.startswith("image/"):

        raise HTTPException(
            status_code=400,
            detail="The uploaded file is not a valid image."
        )

    image_bytes = await leafImage.read()

    if not image_bytes:
        raise HTTPException(
            status_code=400,
            detail="Uploaded image is empty."
        )

    try:
        # Verify that the uploaded file is a valid image
        pil_image = Image.open(
            io.BytesIO(image_bytes)
        ).convert("RGB")

    except Exception:

        raise HTTPException(
            status_code=400,
            detail="Unable to read the uploaded image."
        )

    local_result = None
    local_predicted_invalid = False

    # -----------------------------------------------------
    # STEP 1: LOCAL MODEL INFERENCE
    # -----------------------------------------------------

    if model is not None and processor is not None:

        try:

            inputs = processor(
                images=pil_image,
                return_tensors="pt"
            ).to(DEVICE)

            with torch.no_grad():

                outputs = model(**inputs)

                probs = torch.nn.functional.softmax(
                    outputs.logits[0],
                    dim=0
                )

                confidence, predicted_idx = torch.max(
                    probs,
                    dim=0
                )

            raw_label = model.config.id2label[
                predicted_idx.item()
            ]

            conf_percentage = round(
                confidence.item() * 100,
                1
            )

            print(
                f"Local prediction: {raw_label} "
                f"| Confidence: {conf_percentage}%"
            )

            # Check invalid or low-confidence prediction
            if (
                raw_label.strip().lower() == "invalid"
                or conf_percentage < 65.0
            ):

                local_predicted_invalid = True

            else:

                parts = raw_label.split("___")

                plant_name = (
                    parts[0]
                    .replace("_", " ")
                    .title()
                )

                disease_name = (
                    parts[1].replace("_", " ").title()
                    if len(parts) > 1
                    else "Healthy"
                )

                is_healthy = (
                    "healthy" in disease_name.lower()
                )

                enriched = enrich_local_prediction(
                    plant_name,
                    disease_name,
                    is_healthy
                )

                local_result = {

                    "plantName": plant_name,

                    "conditionName": disease_name,

                    "healthStatus": (
                        "Healthy" if is_healthy else "Infected"
                    ),

                    "pathogenType": (
                        "None" if is_healthy else "Fungal/Bacterial"
                    ),

                    "confidenceScore": conf_percentage,

                    "severityRating": (
                        "None"
                        if is_healthy
                        else (
                            "Severe"
                            if conf_percentage > 85
                            else "Moderate"
                        )
                    ),

                    "symptoms": enriched.get("symptoms", []),

                    "causes": enriched.get("causes", []),

                    "treatments": enriched.get("treatments", []),

                    "organicRemedies": enriched.get(
                        "organicRemedies", []
                    ),

                    "preventions": enriched.get("preventions", [])
                }

        except Exception as error:

            print(
                "Local model inference error:",
                repr(error)
            )

            local_predicted_invalid = True

    else:

        print("Local model unavailable. Using Gemini fallback.")

        local_predicted_invalid = True

    # -----------------------------------------------------
    # STEP 2: GEMINI UNIVERSAL DIAGNOSIS
    # -----------------------------------------------------

    if local_predicted_invalid or not local_result:

        print(
            "Routing specimen to Universal "
            "Tree & Plant Diagnostician..."
        )

        gemini_result = diagnose_with_gemini(
            image_bytes,
            leafImage.content_type
        )

        if gemini_result:

            return JSONResponse(
                content=gemini_result
            )

    # -----------------------------------------------------
    # STEP 3: RETURN LOCAL MODEL RESULT
    # -----------------------------------------------------

    if local_result:

        return JSONResponse(
            content=local_result
        )

    # -----------------------------------------------------
    # STEP 4: FINAL FALLBACK
    # -----------------------------------------------------

    return JSONResponse(
        content={

            "plantName": "Unrecognized Tree / Specimen",

            "conditionName": "Specimen Out of Model Scope",

            "healthStatus": "Inconclusive",

            "pathogenType": "None",

            "confidenceScore": 0.0,

            "severityRating": "None",

            "symptoms": [
                "The uploaded specimen could not be classified "
                "by the local model or Gemini."
            ],

            "causes": [
                "The specimen may be unsupported or the "
                "diagnosis services may be unavailable."
            ],

            "treatments": [
                "Try another clear image showing the entire leaf "
                "and its visible symptoms."
            ],

            "organicRemedies": [
                "No treatment recommendation is available "
                "without a reliable diagnosis."
            ],

            "preventions": [
                "Ensure leaves are centered under clear "
                "natural lighting."
            ]
        }
    )


# =========================================================
# 7. SERVE FRONTEND
# =========================================================

app.mount(
    "/",
    StaticFiles(
        directory="public",
        html=True
    ),
    name="public"
)


# =========================================================
# 8. START SERVER
# =========================================================

if __name__ == "__main__":

    import uvicorn

    port = int(
        os.environ.get("PORT", 8000)
    )

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )
