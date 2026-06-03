import networkx as nx
import pandas as pd
import community as community_louvain

class GraphEngine:
    def __init__(self):
        self.G = nx.DiGraph()

    def build_graph(self, edges_df: pd.DataFrame):
        for _, row in edges_df.iterrows():
            self.G.add_edge(row['source_id'], row['target_id'])
        print(f"[GraphEngine] Граф построен: {self.G.number_of_nodes()} узлов, {self.G.number_of_edges()} рёбер")

    def extract_features(self) -> pd.DataFrame:
        G_und     = self.G.to_undirected()
        in_deg    = dict(self.G.in_degree())
        out_deg   = dict(self.G.out_degree())
        clust     = nx.clustering(G_und)
        pr        = nx.pagerank(self.G, alpha=0.85)
        between   = nx.betweenness_centrality(self.G, normalized=True)
        partition = community_louvain.best_partition(G_und)

        features = []
        for node in self.G.nodes():
            in_d  = in_deg.get(node, 0)
            out_d = out_deg.get(node, 0)
            features.append({
                'user_id':      node,
                'in_degree':    in_d,
                'out_degree':   out_d,
                'ff_ratio':     out_d / (in_d + 1),
                'clustering':   clust.get(node, 0),
                'pagerank':     pr.get(node, 0),
                'betweenness':  between.get(node, 0),
                'community_id': partition.get(node, -1),
            })
        return pd.DataFrame(features)