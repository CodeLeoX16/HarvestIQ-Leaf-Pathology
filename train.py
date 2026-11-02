import json
import torch
import torch.nn as nn
from torchvision import models, transforms
from torch.utils.data import DataLoader, Dataset
from datasets import load_dataset
from PIL import Image

BATCH_SIZE = 32
EPOCHS = 3
LEARNING_RATE = 0.001
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

class PlantVillageDataset(Dataset):
    def __init__(self, hf_split, transform=None):
        self.data = hf_split
        self.transform = transform

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        item = self.data[idx]
        image = item["image"]

        if image.mode != "RGB":
            image = image.convert("RGB")

        if self.transform:
            image = self.transform(image)

        label = item["label"]
        return image, torch.tensor(label, dtype=torch.long)

def main():
    print(f"Executing training on: {DEVICE}")
    print("Loading verified image dataset 'mrsnd/PlantVillage' from Hugging Face...")

    # Load dataset that contains genuine PIL image objects
    hf_dataset = load_dataset("mrsnd/PlantVillage")
    
    # Check splits
    if "validation" in hf_dataset:
        train_hf = hf_dataset["train"]
        test_hf = hf_dataset["validation"]
    elif "test" in hf_dataset:
        train_hf = hf_dataset["train"]
        test_hf = hf_dataset["test"]
    else:
        split = hf_dataset["train"].train_test_split(test_size=0.2, seed=42)
        train_hf = split["train"]
        test_hf = split["test"]

    # Extract label names
    features = train_hf.features
    if "label" in features and hasattr(features["label"], "names"):
        unique_classes = features["label"].names
    else:
        # Fallback if labels are raw strings
        unique_classes = sorted(list(set(train_hf["label"])))

    num_classes = len(unique_classes)
    print(f"Loaded {len(train_hf)} training images across {num_classes} classes.")

    # Image Transforms
    train_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])

    test_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])

    train_data = PlantVillageDataset(train_hf, transform=train_transform)
    test_data = PlantVillageDataset(test_hf, transform=test_transform)

    # num_workers=0 is required on Windows
    train_loader = DataLoader(train_data, batch_size=BATCH_SIZE, shuffle=True, num_workers=0)
    test_loader = DataLoader(test_data, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)

    # MobileNetV2 with Transfer Learning
    model = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.DEFAULT)
    for param in model.features.parameters():
        param.requires_grad = False

    model.classifier[1] = nn.Linear(model.last_channel, num_classes)
    model = model.to(DEVICE)

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.classifier.parameters(), lr=LEARNING_RATE)

    print("\nStarting Training...")
    for epoch in range(EPOCHS):
        model.train()
        running_loss = 0.0
        correct = 0
        total = 0

        for batch_idx, (images, targets) in enumerate(train_loader):
            images, targets = images.to(DEVICE), targets.to(DEVICE)

            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()

            running_loss += loss.item() * images.size(0)
            _, preds = torch.max(outputs, 1)
            correct += (preds == targets).sum().item()
            total += targets.size(0)

            if (batch_idx + 1) % 50 == 0:
                print(f"Epoch [{epoch+1}/{EPOCHS}] | Step [{batch_idx+1}/{len(train_loader)}] Loss: {loss.item():.4f}")

        epoch_acc = (correct / total) * 100
        print(f"=== Epoch [{epoch+1}/{EPOCHS}] Train Accuracy: {epoch_acc:.2f}% ===")

    # Save weights
    torch.save(model.state_dict(), "model.pth")
    print("\nModel saved to 'model.pth'.")

    # Generate classes.json for HarvestIQ Server
    metadata = {}
    for name in unique_classes:
        name_str = str(name)
        parts = name_str.split("___") if "___" in name_str else [name_str, "Healthy"]
        plant = parts[0]
        condition = parts[1] if len(parts) > 1 else "Healthy"
        is_healthy = "healthy" in condition.lower()

        metadata[name_str] = {
            "plantName": plant.replace("_", " "),
            "conditionName": condition.replace("_", " "),
            "healthStatus": "Healthy" if is_healthy else "Infected",
            "pathogenType": "None" if is_healthy else "Fungal/Bacterial",
            "symptoms": ["Normal turgor, uniform green blade."] if is_healthy else ["Visible lesions, necrotic leaf spots, or chlorosis."],
            "treatments": ["Maintain standard N-P-K feeding schedule."] if is_healthy else ["Isolate affected leaves and apply targeted bio-fungicide or copper spray."],
            "preventions": ["Continue standard garden hygiene."] if is_healthy else ["Avoid overhead leaf irrigation. Ensure optimal canopy aeration."]
        }

    with open("classes.json", "w") as f:
        json.dump({"classes": unique_classes, "database": metadata}, f, indent=2)

    print("Metadata written to 'classes.json'. Ready for server.py!")

if __name__ == "__main__":
    main()