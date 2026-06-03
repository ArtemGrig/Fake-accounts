import os
import sys
import pandas as pd
from graph_engine      import GraphEngine
from activity_analyzer import ActivityAnalyzer
from classifier        import FakeAccountClassifier
from visualizer        import Visualizer

def analyze(users, edges, activity, output='results/report.csv'):
    os.makedirs('results', exist_ok=True)

    print("\n=== Загрузка данных ===")
    users_df    = pd.read_csv(users)
    edges_df    = pd.read_csv(edges)
    activity_df = pd.read_csv(activity)
    print(f"Пользователей: {len(users_df)} | Рёбер: {len(edges_df)} | Событий: {len(activity_df)}")

    print("\n=== Анализ графа ===")
    engine = GraphEngine()
    engine.build_graph(edges_df)
    g_feat = engine.extract_features()

    print("\n=== Анализ активности ===")
    analyzer = ActivityAnalyzer()
    b_feat   = analyzer.extract_features(activity_df)

    print("\n=== Классификация ===")
    all_feat = g_feat.merge(b_feat, on='user_id', how='left').fillna(0)
    clf      = FakeAccountClassifier(contamination=0.1)
    results  = clf.fit_predict(all_feat)

    results = results.merge(users_df[['user_id','username']], on='user_id', how='left')

    n_fake = results['is_fake'].sum()
    print(f"\n{'='*50}")
    print(f"РЕЗУЛЬТАТ: обнаружено {n_fake} подозрительных из {len(results)} ({n_fake/len(results)*100:.1f}%)")
    print(f"{'='*50}")

    print("\nТОП подозрительных аккаунтов:")
    top = results[results['is_fake'] == 1].sort_values('final_score', ascending=False)
    print(top[['user_id','username','final_score','ff_ratio','burst_score']].to_string(index=False))

    results.to_csv(output, index=False)
    print(f"\n[ОТЧЁТ] Сохранён: {output}")

    print("\n=== Визуализация ===")
    Visualizer().plot_graph(engine.G, results, 'results/graph_visualization.html')
    print("\nГотово! Открой файл results/graph_visualization.html в браузере.")

if __name__ == '__main__':
    analyze(
        users    = 'data/users.csv',
        edges    = 'data/edges.csv',
        activity = 'data/activity_log.csv'
    )