
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

class Graph:
    """
    The Graph to model the skeletons extracted by the openpose
    Args:
        strategy (string): must be one of the follow candidate
        - uniform: Uniform Labeling
        - distance: Distance Partitioning
        - spatial: Spatial Configuration
        For valid strategy, please refer to the paper:
        https://arxiv.org/abs/1801.07455
    """

    def __init__(self, strategy='spatial'):
        self.num_node = 25
        self.edges = self.get_edges()
        self.center = 0 # Hip center usually

        self.strategy = strategy
        self.A = self.get_adjacency_matrix(strategy)

    def get_edges(self):
        # 25 main joints mapped from MediaPipe (33 -> 25 simplified skeleton)
        # 0: nose, 1: left_eye_inner, 2: left_eye, 3: left_eye_outer, 4: right_eye_inner, ...
        # Standard MediaPipe to NTU-RGB+D style 25 joints mapping is common or custom.
        # Here we define a standard human skeleton connectivity.
        # Assuming 0 is center hip/root for simplicity or sticking to MP topology subset.
        
        # Let's use a standard generic human skeleton connectivity (indices 0-24)
        # This is strictly topological.
        # Example connectivity for a body:
        # Torso: 0-1, 1-20, 20-2, 2-3 (spine like)
        # Arms: 20-4, 4-5, 5-6, 6-7, 7-21, 6-22 (shoulder->hand)
        # Legs: 0-16, 16-17, 17-18, 18-19 (hip->foot)
        
        # NOTE: Since the prompt asks for "25 major joints", I will use the
        # NTU-RGB+D style connectivity which is common for STGCN papers.
        # 0: base of spine
        # 1: mid spine
        # 2: neck
        # 3: head
        # 4,5,6,7: Left arm (shoulder, elbow, wrist, hand)
        # 8,9,10,11: Right arm
        # 12,13,14,15: Left leg (hip, knee, ankle, foot)
        # 16,17,18,19: Right leg
        # 20: Spine shoulder
        # 21: Tip of left hand
        # 22: Thumb of left hand
        # 23: Tip of right hand
        # 24: Thumb of right hand
        
        neighbor_link = [
            (0, 1), (1, 20), (20, 2), (2, 3), # Spine
            (20, 4), (4, 5), (5, 6), (6, 7), (7, 21), (6, 22), # Left Arm
            (20, 8), (8, 9), (9, 10), (10, 11), (11, 23), (10, 24), # Right Arm
            (0, 12), (12, 13), (13, 14), (14, 15), # Left Leg
            (0, 16), (16, 17), (17, 18), (18, 19)  # Right Leg
        ]
        self_link = [(i, i) for i in range(self.num_node)]
        return neighbor_link + self_link

    def get_adjacency_matrix(self, strategy):
        valid_hop = 1
        adj = np.zeros((self.num_node, self.num_node))

        for i, j in self.edges:
            adj[i, j] = 1
            adj[j, i] = 1
        
        # Normalize
        if strategy == 'spatial':
            A = []
            for i in range(valid_hop + 1):
                A.append(np.zeros((self.num_node, self.num_node)))
            
            # This is a simplified spatial strategy implementation
            # Root node (center)
            # 1-hop neighbors closer to center
            # 1-hop neighbors further from center
            # For simplicity in this generated code, we implement the
            # "Uniform" normalization (D^-1/2 (A+I) D^-1/2) extended to partitions if needed.
            # But the prompt asks for: H' = D^-1/2 (A+I) D^-1/2 HW which is standard GCN.
            # So let's stick to simple normalized adjacency for the basic GCN formula requested.
            
            # Standard GCN normalization
            # A_hat = A + I
            # D_hat = sum(A_hat)
            # A_norm = D_hat^-0.5 * A_hat * D_hat^-0.5
            
            # Resetting adj to 0-1 without self loops first for calculation
            adj = np.zeros((self.num_node, self.num_node))
            link_mat = self.get_edges()
            for (i, j) in link_mat:
                if i != j:
                    adj[i, j] = 1
                    adj[j, i] = 1
            
            # A + I
            adj_hat = adj + np.eye(self.num_node)
            
            # D^-1/2
            clean_adj = adj_hat
            row_sum = np.sum(clean_adj, axis=1)
            d_inv_sqrt = np.power(row_sum, -0.5).flatten()
            d_inv_sqrt[np.isinf(d_inv_sqrt)] = 0.
            d_mat_inv_sqrt = np.diag(d_inv_sqrt)
            
            # Normalized A
            norm_adj = d_mat_inv_sqrt.dot(clean_adj).dot(d_mat_inv_sqrt)
            
            # Shape (1, V, V) so it broadcasts over Batch/Channels
            # Or (K, V, V) if using partitions. The prompt suggests a simple formula,
            # so we'll return a single matrix (1, V, V) or just (V, V).
            return torch.tensor(norm_adj, dtype=torch.float32).unsqueeze(0)

        else:
            raise ValueError("Only 'spatial' strategy implemented for this demo")

class STGCN_Block(nn.Module):
    def __init__(self, in_channels, out_channels, A, stride=1, dropout=0):
        super().__init__()
        
        self.A = A # (K, V, V) or (1, V, V)
        # If A has K partitions, input to conv is in_channels * K? 
        # Standard STGCN uses K partitions (kernel size for graph conv).
        # We will assume A is (1, V, V) based on the simple formula given, 
        # or we treat the graph conv as a simple matmul.
        
        # But for robustness, usually STGCN uses K=3 (root, centripetal, centrifugal).
        # We'll use kernel_size=1 (spatial) for a vanilla GCN as requested by the specific formula:
        # H' = D^-1/2 (A+I) D^-1/2 HW
        
        self.gcn_conv = nn.Conv2d(
            in_channels,
            out_channels,
            kernel_size=1) 
            # 1x1 conv corresponds to 'W' in HW. 
            # The matrix multiplication with A happens in forward.

        self.tcn = nn.Sequential(
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(
                out_channels,
                out_channels,
                (9, 1),
                (stride, 1),
                padding=(4, 0)
            ),
            nn.BatchNorm2d(out_channels),
            nn.Dropout(dropout, inplace=True),
        )

        # Residual
        if in_channels != out_channels or stride != 1:
            self.residual = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, kernel_size=1, stride=(stride, 1)),
                nn.BatchNorm2d(out_channels)
            )
        else:
            self.residual = nn.Identity()

        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        # x: (N, C, T, V)
        N, C, T, V = x.size()
        
        # Spatial GCN
        # Formula: H' = A * H * W
        # Implementation: W is 1x1 conv over features. A is matmul over V.
        
        # 1. Transform features (H * W)
        x_gcn = self.gcn_conv(x) # (N, out_C, T, V)
        
        # 2. Graph Convolution (Multiply by A)
        # x_gcn: (N, C_out, T, V) -> permute to (N, C_out, T, V) for matmul
        # We want to multiply A (V, V) with x's last dimension V.
        # A matrix multiplication: (N, C, T, V) @ (V, V) -> (N, C, T, V)
        
        # Ensure A is on correct device
        if self.A.device != x.device:
            self.A = self.A.to(x.device)
            
        A = self.A[0] # Take the single matrix (V, V)
        
        # Einsum is cleaner: nctv, vw -> nctw (where w=v)
        x_gcn = torch.einsum('nctv,vw->nctw', x_gcn, A)
        
        # Temporal GCN
        x_tcn = self.tcn(x_gcn)

        # Residual
        x_res = self.residual(x)
        
        return self.relu(x_tcn + x_res)


class STGCN_Encoder(nn.Module):
    def __init__(self, in_channels=3, num_class=128, graph_args={'strategy': 'spatial'}, edge_importance_weighting=True):
        super().__init__()

        # Graph
        self.graph = Graph(**graph_args)
        A = self.graph.A

        # Backbone
        # 64 -> 64 -> 128 -> 256
        self.data_bn = nn.BatchNorm1d(in_channels * 25) # normalize input
        
        self.st_gcn_networks = nn.ModuleList((
            STGCN_Block(in_channels, 64, A, stride=1),
            STGCN_Block(64, 64, A, stride=1),
            STGCN_Block(64, 128, A, stride=1), # Typically stride=2 to downsample time? User didn't specify, sticking to 1 or 2. Let's do 1 to keep T=32 or 2 to reduce.
            # User said "Stack: ... 64 -> 64 -> 128 -> 256" without mentioning stride.
            # Usually we reduce temporal dimension. Let's keep T=32 for simplicity unless required.
            STGCN_Block(128, 256, A, stride=1),
        ))

        # Heads
        # Global Pooling (Space V + Time T) -> 256 vector
        # Projection Head: 256 -> 128 (MLP)
        self.fc_head = nn.Sequential(
            nn.Linear(256, 128),
            nn.ReLU(inplace=True),
            nn.Linear(128, 128) # Output dim for SimCLR embeddings
        )

    def forward(self, x):
        # Input: N, C, T, V
        N, C, T, V = x.size()
        
        # Data Normalization (BatchNorm over Channels*Vertices)
        # N, C, T, V -> N, V, C, T -> N, V*C, T
        x = x.permute(0, 3, 1, 2).contiguous().view(N, V * C, T)
        x = self.data_bn(x)
        # N, V*C, T -> N, V, C, T -> N, C, T, V
        x = x.view(N, V, C, T).permute(0, 2, 3, 1).contiguous()
        
        # Forward GCNs
        for gcn in self.st_gcn_networks:
            x = gcn(x)
        
        # x is now (N, 256, T, V)
        
        # Global Pooling
        # Average across V and T
        x = F.avg_pool2d(x, x.size()[2:]) # Pool T(2) and V(3) -> (N, 256, 1, 1)
        x = x.view(N, -1) # (N, 256)

        # Projection Head
        embedding = self.fc_head(x) # (N, 128)
        
        return embedding

if __name__ == "__main__":
    # Quick Test
    model = STGCN_Encoder()
    dummy_input = torch.randn(2, 3, 32, 25) # N=2, C=3, T=32, V=25
    output = model(dummy_input)
    print(f"Model Output Shape: {output.shape}") # Should be (2, 128)
