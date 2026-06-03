import pandas as pd
from scipy.stats import entropy

class ActivityAnalyzer:
    def extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['hour'] = df['timestamp'].dt.hour
        results = []

        for user_id, g in df.groupby('user_id'):
            h_active = g['timestamp'].dt.floor('h').nunique()
            avg_ph   = len(g) / (h_active + 1)
            night_r  = len(g[g['hour'].between(0, 5)]) / (len(g) + 1)
            act_ent  = entropy(g['action_type'].value_counts(normalize=True))
            min_cnt  = g.groupby(g['timestamp'].dt.floor('min')).size()
            burst    = (min_cnt > 8).sum() / (len(min_cnt) + 1)
            results.append({
                'user_id':              user_id,
                'avg_actions_per_hour': avg_ph,
                'night_activity_ratio': night_r,
                'action_entropy':       act_ent,
                'burst_score':          burst,
                'total_actions':        len(g),
            })
        return pd.DataFrame(results)