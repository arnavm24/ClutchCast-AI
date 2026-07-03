from ui.formatting import render_html


def apply_custom_css() -> None:
    render_html(
        """
        <style>
        :root { --panel:#101621; --line:#263244; --text:#F8FAFC; --muted:#94A3B8; }
        .stApp { background: radial-gradient(circle at top left, #162033 0, #070A12 34%, #05070D 100%); color: var(--text); }
        [data-testid="stSidebar"] { background-color:#070A12; border-right:1px solid #1F2937; }
        .block-container { padding-top:3.15rem; padding-bottom:2rem; max-width:1500px; }
        h1, h2, h3 { letter-spacing:0; }
        .eyebrow { color:#8EA0BA; font-size:.72rem; text-transform:uppercase; letter-spacing:.14em; font-weight:800; }
        .brand-header { display:flex; align-items:center; justify-content:space-between; gap:18px; margin:.8rem 0 18px; }
        .brand-left { display:flex; align-items:center; gap:14px; }
        .brand-mark { width:54px; height:54px; border-radius:18px; position:relative; display:flex; align-items:center; justify-content:center; color:#F8FAFC; font-weight:950; background:radial-gradient(circle at 30% 25%, #FDBA74 0, #F97316 38%, #1D4ED8 100%); box-shadow:0 16px 45px rgba(29,78,216,.32); overflow:hidden; }
        .brand-mark:before { content:""; position:absolute; inset:10px; border:2px solid rgba(255,255,255,.42); border-radius:50%; }
        .brand-mark:after { content:""; position:absolute; width:92px; height:2px; background:rgba(255,255,255,.38); transform:rotate(-28deg); }
        .brand-cc { position:relative; z-index:2; font-size:1.15rem; text-shadow:0 2px 10px rgba(0,0,0,.5); }
        .brand-title { font-size:2.05rem; line-height:1; font-weight:950; color:#F8FAFC; letter-spacing:-.03em; }
        .brand-subtitle { margin-top:5px; color:#9FB0C8; font-size:.88rem; }
        .brand-badge, .status-badge { border:1px solid rgba(148,163,184,.22); background:rgba(15,23,42,.72); border-radius:999px; padding:8px 12px; color:#CBD5E1; font-size:.82rem; font-weight:800; display:inline-block; }
        .status-ok { color:#BBF7D0; border-color:rgba(34,197,94,.35); background:rgba(22,101,52,.24); }
        .status-bad { color:#FECACA; border-color:rgba(239,68,68,.35); background:rgba(127,29,29,.28); }
        .hero-shell { border:1px solid rgba(148,163,184,.22); background:linear-gradient(135deg, rgba(16,22,34,.96), rgba(6,10,18,.98)); border-radius:20px; padding:20px; box-shadow:0 24px 80px rgba(0,0,0,.42); }
        .scoreboard { display:grid; grid-template-columns:1fr 190px 1fr; gap:18px; align-items:center; }
        .team-box { min-height:188px; border:1px solid rgba(148,163,184,.18); border-radius:18px; padding:18px; background:linear-gradient(145deg, rgba(255,255,255,.055), rgba(255,255,255,.02)); display:flex; align-items:center; gap:18px; }
        .team-box.home { flex-direction:row-reverse; text-align:right; }
        .team-logo-wrap, .team-fallback { width:76px; height:76px; border-radius:50%; display:flex; align-items:center; justify-content:center; flex:0 0 auto; }
        .team-logo-wrap { background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.18); overflow:hidden; }
        .team-logo { width:68px; height:68px; object-fit:contain; filter:drop-shadow(0 8px 20px rgba(0,0,0,.45)); }
        .team-fallback { font-weight:900; color:#07111F; background:#E5E7EB; }
        .team-name { color:#AAB7CA; font-size:.82rem; text-transform:uppercase; letter-spacing:.11em; font-weight:800; }
        .team-score { font-size:4.55rem; line-height:.92; font-weight:900; color:#F8FAFC; }
        .team-prob-label { margin-top:12px; color:#8EA0BA; font-size:.72rem; text-transform:uppercase; letter-spacing:.12em; font-weight:800; }
        .team-prob-big { font-size:2.5rem; line-height:1; font-weight:900; color:#F8FAFC; margin-top:2px; }
        .clock-card { border-radius:18px; padding:22px 14px; text-align:center; background:rgba(5,9,16,.82); border:1px solid rgba(148,163,184,.18); }
        .clock-value { font-size:2.05rem; font-weight:900; color:white; }
        .clock-label { color:#94A3B8; font-size:.78rem; text-transform:uppercase; letter-spacing:.16em; }
        .model-pill { display:inline-block; margin-top:12px; padding:6px 10px; border-radius:999px; background:rgba(59,130,246,.14); border:1px solid rgba(59,130,246,.32); color:#BFDBFE; font-size:.74rem; font-weight:800; }
        .wp-wrap { margin-top:18px; }
        .wp-row { display:flex; justify-content:space-between; color:#DDE7F4; font-weight:900; margin-bottom:8px; font-size:1.15rem; }
        .wp-row strong { font-size:1.9rem; line-height:1; }
        .wp-bar { height:24px; border-radius:999px; overflow:hidden; display:flex; background:#111827; border:1px solid rgba(148,163,184,.22); }
        .wp-away, .wp-home { height:100%; }
        .metric-grid, .summary-grid, .story-grid, .insight-grid, .recap-grid { display:grid; gap:14px; margin:14px 0 18px; }
        .metric-grid, .summary-grid { grid-template-columns:repeat(4, minmax(0, 1fr)); }
        .story-grid { grid-template-columns:1.35fr 1fr 1fr; }
        .insight-grid, .recap-grid { grid-template-columns:repeat(2, minmax(0, 1fr)); }
        .metric-card, .intel-card, .live-card, .summary-card, .empty-card, .story-shell, .insight-card { border:1px solid rgba(148,163,184,.18); background:rgba(15,23,42,.78); border-radius:16px; padding:16px; min-height:116px; }
        .metric-label, .summary-label, .card-kicker { color:#94A3B8; font-size:.74rem; text-transform:uppercase; letter-spacing:.12em; font-weight:800; }
        .metric-value, .summary-value, .card-value { color:#F8FAFC; font-size:1.36rem; line-height:1.15; font-weight:900; margin-top:8px; }
        .summary-value.big, .card-value.big { font-size:1.7rem; }
        .metric-detail, .summary-detail, .card-detail, .intel-body { color:#A7B4C8; font-size:.88rem; line-height:1.4; margin-top:8px; }
        .tab-intro { color:#AEBBD0; margin:0 0 14px; max-width:950px; }
        .story-title, .intel-title { color:#E2E8F0; font-weight:900; margin-bottom:6px; }
        .story-lede { color:#D7E3F4; font-size:.98rem; line-height:1.45; margin-bottom:12px; }
        .icon-pill, .avatar { width:42px; height:42px; display:flex; align-items:center; justify-content:center; font-weight:950; color:white; }
        .icon-pill { border-radius:14px; background:rgba(59,130,246,.18); color:#DBEAFE; font-size:1.2rem; margin-bottom:10px; }
        .avatar { border-radius:50%; background:linear-gradient(135deg,#F97316,#2563EB); box-shadow:0 12px 28px rgba(37,99,235,.25); }
        .player-chip { display:flex; align-items:center; gap:12px; }
        .section-card { border:1px solid rgba(148,163,184,.16); background:rgba(15,23,42,.62); border-radius:18px; padding:16px; }
        .right-rail-spacer { height:56px; }
        div[data-testid="stMetric"] { background:rgba(15,23,42,.78); border:1px solid rgba(148,163,184,.16); padding:1rem; border-radius:14px; }
        .stTabs [data-baseweb="tab-list"] { gap:.35rem; margin-top:.35rem; flex-wrap:wrap; }
        .stTabs [data-baseweb="tab"] { background:rgba(15,23,42,.66); border-radius:999px; color:#CBD5E1; padding:.5rem 1rem; }
        .stTabs [aria-selected="true"] { background:#E5E7EB !important; color:#111827 !important; }

        /* Data-quality banner (Live Game Center) */
        .quality-banner { display:flex; align-items:center; gap:14px; border-radius:14px; padding:12px 16px; margin:0 0 14px; border:1px solid; font-weight:800; }
        .quality-banner .q-title { font-size:.95rem; letter-spacing:.04em; text-transform:uppercase; }
        .quality-banner .q-detail { font-size:.82rem; font-weight:600; opacity:.88; margin-top:2px; }
        .quality-banner .q-dot { width:12px; height:12px; border-radius:50%; flex:0 0 auto; box-shadow:0 0 12px currentColor; }
        .quality-full { color:#BBF7D0; border-color:rgba(34,197,94,.45); background:rgba(22,101,52,.22); }
        .quality-historical { color:#BFDBFE; border-color:rgba(59,130,246,.45); background:rgba(30,58,138,.24); }
        .quality-fallback { color:#FDE68A; border-color:rgba(245,158,11,.45); background:rgba(120,53,15,.24); }
        .quality-missing { color:#FECACA; border-color:rgba(239,68,68,.5); background:rgba(127,29,29,.28); }
        .quality-replay { color:#E9D5FF; border-color:rgba(168,85,247,.45); background:rgba(88,28,135,.26); }
        .quality-chip { display:inline-block; margin-left:auto; padding:4px 10px; border-radius:999px; border:1px solid rgba(148,163,184,.35); background:rgba(15,23,42,.6); color:#CBD5E1; font-size:.72rem; font-weight:800; }
        .run-chip { display:inline-block; padding:6px 12px; border-radius:999px; font-weight:900; font-size:.9rem; border:1px solid rgba(255,255,255,.25); }

        /* Player matchup cards */
        .player-card { border:1px solid rgba(148,163,184,.2); border-top:4px solid var(--accent, #3B82F6); background:linear-gradient(160deg, rgba(16,22,34,.96), rgba(6,10,18,.98)); border-radius:18px; padding:18px; }
        .player-card-head { display:flex; align-items:center; gap:16px; margin-bottom:12px; }
        .headshot-wrap { position:relative; width:84px; height:84px; border-radius:50%; overflow:hidden; flex:0 0 auto; border:2px solid var(--accent, #3B82F6); background:rgba(255,255,255,.06); }
        .headshot-fallback { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; font-weight:950; font-size:1.5rem; color:white; background:linear-gradient(135deg,#F97316,#2563EB); }
        .headshot-img { position:absolute; inset:0; width:100%; height:100%; object-fit:cover; object-position:top; }
        .player-card-name { font-size:1.3rem; font-weight:950; color:#F8FAFC; line-height:1.1; }
        .player-card-team { color:#94A3B8; font-size:.78rem; text-transform:uppercase; letter-spacing:.12em; font-weight:800; margin-top:4px; }
        .player-stat-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:12px; }
        .player-stat { border:1px solid rgba(148,163,184,.14); background:rgba(15,23,42,.6); border-radius:12px; padding:10px 12px; }
        .player-stat .p-label { color:#8EA0BA; font-size:.68rem; text-transform:uppercase; letter-spacing:.1em; font-weight:800; }
        .player-stat .p-value { color:#F8FAFC; font-size:1.22rem; font-weight:900; margin-top:4px; }
        .split-bar { display:flex; height:14px; border-radius:999px; overflow:hidden; background:#111827; border:1px solid rgba(148,163,184,.2); margin-top:8px; }
        .split-pos { background:linear-gradient(90deg,#22C55E,#4ADE80); }
        .split-neg { background:linear-gradient(90deg,#F87171,#EF4444); }
        .split-legend { display:flex; justify-content:space-between; color:#94A3B8; font-size:.74rem; margin-top:5px; font-weight:700; }
        .top-play { border-left:3px solid var(--accent, #3B82F6); background:rgba(15,23,42,.6); border-radius:0 12px 12px 0; padding:10px 12px; margin-top:12px; color:#CBD5E1; font-size:.86rem; line-height:1.4; }
        .top-play .tp-kicker { color:#8EA0BA; font-size:.68rem; text-transform:uppercase; letter-spacing:.1em; font-weight:800; margin-bottom:4px; }

        /* Why panel drivers */
        .driver-row { display:flex; align-items:center; gap:10px; padding:7px 0; border-bottom:1px solid rgba(148,163,184,.1); }
        .driver-name { color:#DDE7F4; font-size:.88rem; font-weight:700; flex:1; }
        .driver-value { color:#94A3B8; font-size:.8rem; }
        .driver-arrow { font-weight:950; font-size:1rem; width:22px; text-align:center; }
        .driver-up { color:#4ADE80; }
        .driver-down { color:#F87171; }

        /* Sidebar demo + drama */
        .demo-tagline { color:#8EA0BA; font-size:.74rem; margin:-6px 0 8px; }
        .drama-row { display:flex; align-items:center; gap:8px; padding:6px 0; border-bottom:1px solid rgba(148,163,184,.12); color:#CBD5E1; font-size:.84rem; }
        .drama-score { font-weight:950; color:#FDE68A; min-width:34px; }

        @media (max-width:980px) { .scoreboard, .metric-grid, .summary-grid, .story-grid, .insight-grid, .recap-grid, .player-stat-grid { grid-template-columns:1fr; } .team-box.home { flex-direction:row; text-align:left; } .brand-header { align-items:flex-start; flex-direction:column; } .right-rail-spacer { height:0; } }
        </style>
        """
    )
