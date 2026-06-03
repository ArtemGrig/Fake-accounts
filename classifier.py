import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

class FakeAccountClassifier:
    FEATURES = [
        'in_degree', 'out_degree', 'ff_ratio', 'clustering',
        'pagerank', 'betweenness', 'avg_actions_per_hour',
        'night_activity_ratio', 'action_entropy', 'burst_score'
    ]

    def __init__(self, contamination=0.1):
        self.scaler = StandardScaler()
        self.model  = IsolationForest(
            contamination=contamination,
            n_estimators=200,
            random_state=42
        )

    def fit_predict(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy().fillna(0)
        X  = self.scaler.fit_transform(df[self.FEATURES])
        scores    = self.model.fit(X).decision_function(X)
        norm_sc   = 1 - (scores - scores.min()) / (scores.max() - scores.min() + 1e-9)
        rule_flag = (
            (df.get('ff_ratio', 0) > 20) |
            (df.get('burst_score', 0) > 0.2) |
            (df.get('in_degree', 0) == 0)
        ).astype(int)
        df['iso_score']   = norm_sc
        df['rule_flag']   = rule_flag
        df['final_score'] = 0.6 * norm_sc + 0.4 * rule_flag
        df['is_fake']     = (df['final_score'] > 0.6).astype(int)
        return df