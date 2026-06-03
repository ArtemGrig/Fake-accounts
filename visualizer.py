import networkx as nx
import pandas as pd
from pyvis.network import Network

class Visualizer:
    def plot_graph(self, G: nx.DiGraph, results_df: pd.DataFrame, output_path='results/graph_visualization.html'):

        net = Network(height='100vh', width='100%', directed=True, bgcolor='#0f0f1a')

        fake_ids = set(results_df[results_df['is_fake'] == 1]['user_id'])

        for node in G.nodes():
            row = results_df[results_df['user_id'] == node]
            score    = round(float(row['final_score'].values[0]), 2) if len(row) else 0.0
            username = str(row['username'].values[0]) if len(row) and 'username' in row.columns else f"user_{node}"
            is_fake  = node in fake_ids

            if is_fake:
                color  = '#ff4444'
                border = '#ff0000'
                shape  = 'dot'
                size   = 22
            else:
                color  = '#44bb44'
                border = '#00ff88'
                shape  = 'dot'
                size   = 14

            label = f"{username}\n{'🚨 БОТ' if is_fake else '✅ OK'}\nScore: {score}"
            title = f"""
                <div style='font-family:Arial; padding:8px; background:#1a1a2e;
                            color:white; border-radius:8px; min-width:160px;'>
                    <b style='color:{"#ff6666" if is_fake else "#66ff99"};'>
                        {"🚨 ПОДОЗРИТЕЛЬНЫЙ" if is_fake else "✅ Легитимный"}
                    </b><br>
                    <hr style='border-color:#444; margin:4px 0'>
                    👤 {username}<br>
                    🆔 ID: {node}<br>
                    📊 Score: <b>{score}</b><br>
                    📤 Подписок: {int(row['out_degree'].values[0]) if len(row) else '—'}<br>
                    📥 Подписчиков: {int(row['in_degree'].values[0]) if len(row) else '—'}<br>
                    ⚡ Burst: {round(float(row['burst_score'].values[0]), 2) if len(row) else '—'}
                </div>
            """

            net.add_node(
                int(node),
                label=label,
                title=title,
                color={'background': color, 'border': border,
                       'highlight': {'background': '#ffffff', 'border': '#ffff00'}},
                size=size,
                shape=shape,
                font={'color': 'white', 'size': 11, 'face': 'Arial'},
                borderWidth=2,
            )

        for u, v in G.edges():
            u_fake = u in fake_ids
            v_fake = v in fake_ids
            if u_fake and v_fake:
                color, width = '#ff4444', 2
            elif u_fake or v_fake:
                color, width = '#ff9900', 1.5
            else:
                color, width = '#336633', 0.8

            net.add_edge(int(u), int(v), color=color, width=width, arrows='to')

        net.set_options("""
        {
          "physics": {
            "enabled": true,
            "forceAtlas2Based": {
              "gravitationalConstant": -80,
              "centralGravity": 0.01,
              "springLength": 120,
              "springConstant": 0.08,
              "damping": 0.4
            },
            "solver": "forceAtlas2Based",
            "stabilization": { "iterations": 150 }
          },
          "interaction": {
            "hover": true,
            "tooltipDelay": 100,
            "navigationButtons": true,
            "keyboard": true
          }
        }
        """)

        net.save_graph(output_path)

        with open(output_path, 'r', encoding='utf-8') as f:
            html = f.read()

        n_total = len(results_df)
        n_fake  = len(results_df[results_df['is_fake'] == 1])
        n_ok    = n_total - n_fake

        panel = f"""
        <div style="
            position: fixed; top: 0; left: 0; right: 0; z-index: 9999;
            background: linear-gradient(135deg, #0f0f1a, #1a1a3e);
            color: white; font-family: Arial, sans-serif;
            padding: 12px 24px; display: flex;
            align-items: center; gap: 32px;
            border-bottom: 2px solid #333;
            box-shadow: 0 2px 20px rgba(0,0,0,0.5);
        ">
            <div style="font-size:18px; font-weight:bold; color:#7eb8f7;">
                🔍 Анализ фейковых аккаунтов
            </div>
            <div style="display:flex; gap:20px; margin-left:auto;">
                <div style="text-align:center; background:#1e3a1e; padding:6px 18px; border-radius:20px; border:1px solid #44bb44;">
                    <div style="font-size:22px; font-weight:bold; color:#44ff88;">{n_ok}</div>
                    <div style="font-size:11px; color:#aaa;">✅ Легитимных</div>
                </div>
                <div style="text-align:center; background:#3a1e1e; padding:6px 18px; border-radius:20px; border:1px solid #ff4444;">
                    <div style="font-size:22px; font-weight:bold; color:#ff6666;">{n_fake}</div>
                    <div style="font-size:11px; color:#aaa;">🚨 Подозрительных</div>
                </div>
                <div style="text-align:center; background:#1e1e3a; padding:6px 18px; border-radius:20px; border:1px solid #7eb8f7;">
                    <div style="font-size:22px; font-weight:bold; color:#7eb8f7;">{n_total}</div>
                    <div style="font-size:11px; color:#aaa;">👥 Всего</div>
                </div>
                <div style="text-align:center; background:#2a1e3a; padding:6px 18px; border-radius:20px; border:1px solid #bb88ff;">
                    <div style="font-size:22px; font-weight:bold; color:#cc88ff;">{round(n_fake/n_total*100, 1)}%</div>
                    <div style="font-size:11px; color:#aaa;">📊 Доля ботов</div>
                </div>
            </div>
            <div style="font-size:11px; color:#666; margin-left:16px;">
                🖱 Наводи на узлы · Скролл для зума · Тяни для перемещения
            </div>
        </div>
        <div style="height:60px;"></div>
        """

        html = html.replace('<body>', '<body>' + panel)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

        print(f"[Visualizer] Граф сохранён: {output_path}")