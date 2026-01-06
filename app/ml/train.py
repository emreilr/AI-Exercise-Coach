
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import numpy as np
import random
import os

from app.ml.stgcn import STGCN_Encoder

# Configuration
BATCH_SIZE = 32
LR = 0.01
EPOCHS = 25
TEMP = 0.5 # Temperature for NT-Xent Loss
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
PATIENCE = 5  # Early stopping patience

class PoseGraphDataset(Dataset):
    """
    Dataset that loads pose sequences and applies augmentations for SimCLR.
    
    In a real scenario, this would load from ArangoDB or a pre-processed file.
    For this implementation, we simulate data or load if a path is provided.
    """
    def __init__(self, data=None, transform=None):
        self.transform = transform
        self.data = data if data is not None else self.load_mock_data()
        
    def load_mock_data(self):
        # Mock data generation if no path or for early testing.
        # Shape: (Num_Samples, C=3, T=40, V=25) 
        # T=40 allows temporal crop to T=32
        print("Generating mock training data...")
        return [np.random.randn(3, 40, 25).astype(np.float32) for _ in range(100)] # List of arrays

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        # Return two augmented views of the same sequence
        sequence = self.data[idx]
        
        view_1 = self.augment_sequence(sequence)
        view_2 = self.augment_sequence(sequence)
        
        return torch.from_numpy(view_1), torch.from_numpy(view_2)

    def augment_sequence(self, sequence):
        """
        Applies random augmentations: Jitter, Scale, Shift, Mirror.
        Input: (3, T_orig, 25)
        Output: (3, 32, 25)
        """
        C, T, V = sequence.shape
        T_out = 32
        
        # copy to avoid mutating original
        aug_seq = sequence.copy()
        
        # 1. Temporal Shift (Random Crop)
        if T > T_out:
            start = random.randint(0, T - T_out)
            aug_seq = aug_seq[:, start:start+T_out, :]
        else:
            # Pad if too short (simple zero padding for now)
            # Pad temporal dimension (axis 1)
            pad = T_out - T
            aug_seq = np.pad(aug_seq, ((0,0), (0,pad), (0,0)), mode='constant')
            
        # 2. Scaling (Randomly scale skeleton size)
        if random.random() < 0.5:
            scale_factor = random.uniform(0.8, 1.2)
            aug_seq = aug_seq * scale_factor
            
        # 3. Jittering (Add Gaussian noise)
        if random.random() < 0.5:
            noise = np.random.normal(0, 0.01, aug_seq.shape).astype(np.float32)
            aug_seq = aug_seq + noise
            
        # 4. Mirroring (Flip X coordinate)
        if random.random() < 0.5:
            # Assuming channel 0 is X
            aug_seq[0, :, :] = -aug_seq[0, :, :]
            
        return aug_seq

class NTXentLoss(nn.Module):
    """
    Normalized Temperature-scaled Cross Entropy Loss for SimCLR.
    """
    def __init__(self, temperature=0.5):
        super().__init__()
        self.temperature = temperature
        self.similarity = nn.CosineSimilarity(dim=-1)
        self.criterion = nn.CrossEntropyLoss()

    def forward(self, z_i, z_j):
        # z_i, z_j shape: (Batch, Dim)
        batch_size = z_i.shape[0]
        
        # Concatenate: (2*B, Dim)
        z = torch.cat([z_i, z_j], dim=0)
        
        # Cosine similarity matrix: (2B, 2B)
        # sim[i, j] = cos(z[i], z[j])
        z_norm = F.normalize(z, dim=1)
        sim_matrix = torch.matmul(z_norm, z_norm.T) / self.temperature
        
        # Mask out self-sim
        mask = torch.eye(2 * batch_size, device=z.device).bool()
        sim_matrix.masked_fill_(mask, -9e15)
        
        # Target for i is j (offset by batch_size)
        # For 0: target is B. For 1: target is B+1.
        # For B: target is 0.
        target = torch.cat([
            torch.arange(batch_size, 2 * batch_size, device=z.device),
            torch.arange(0, batch_size, device=z.device)
        ], dim=0)
        
        loss = self.criterion(sim_matrix, target)
        return loss

def train(training_data=None, progress_callback=None, save_path="stgcn_simclr.pth"):
    """
    SimCLR Training Loop.
    args:
        training_data: List of numpy arrays [(3, T, 25), ...]
        progress_callback: function(epoch, total_epochs, loss, message)
        save_path: Path to save the trained model .pth file
    """
    # 1. Dataset & Loader
    dataset = PoseGraphDataset(data=training_data)
    
    # Handle small datasets
    bs = BATCH_SIZE
    if len(dataset) < BATCH_SIZE:
        bs = max(2, len(dataset)) # At least 2 for contrastive
        print(f"Warning: Dataset too small ({len(dataset)}). Reducing batch size to {bs}")
        
    loader = DataLoader(dataset, batch_size=bs, shuffle=True, drop_last=True)
    
    # 2. Model
    model = STGCN_Encoder().to(DEVICE)
    optimizer = optim.Adam(model.parameters(), lr=LR)
    loss_fn = NTXentLoss(temperature=TEMP)
    
    print("Starting SimCLR Training...")
    if progress_callback:
        progress_callback(0, EPOCHS, 0, "Starting Training...")
    
    model.train()
    
    best_loss = float('inf')
    patience_counter = 0
    
    for epoch in range(EPOCHS):
        total_loss = 0
        for x_i, x_j in loader:
            x_i, x_j = x_i.to(DEVICE), x_j.to(DEVICE)
            
            # Zero grad
            optimizer.zero_grad()
            
            # Forward
            z_i = model(x_i)
            z_j = model(x_j)
            
            # Loss
            loss = loss_fn(z_i, z_j)
            
            # Backward
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
            
        avg_loss = total_loss / len(loader)
        print(f"Epoch [{epoch+1}/{EPOCHS}], Loss: {avg_loss:.4f}")
        
        # Update Progress
        if progress_callback:
             progress_callback(epoch + 1, EPOCHS, avg_loss, f"Epoch {epoch+1} complete")
        
        # Checkpoint
        if avg_loss < best_loss:
            best_loss = avg_loss
            patience_counter = 0
            torch.save(model.state_dict(), save_path)
            print(f" -> Model saved (Loss: {best_loss:.4f})")
        else:
            patience_counter += 1
            
        # Early Stopping
        if patience_counter >= PATIENCE:
            print(f"Early stop at epoch {epoch+1}")
            if progress_callback:
                progress_callback(epoch + 1, EPOCHS, avg_loss, f"Early stopping triggered at epoch {epoch+1}")
            break

if __name__ == "__main__":
    train()
