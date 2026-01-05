import pandas as pd
import matplotlib.pyplot as plt

BRAKE_THRESHOLD = 0.05
THROTTLE_THRESHOLD = 0.05
num_segments = 20
segments = range(num_segments)

lap_fast = pd.read_csv("data/lap_fast.csv").sort_values("LapDistPct")
lap_slow = pd.read_csv("data/lap_slow.csv").sort_values("LapDistPct")

def add_segments(df: pd.DataFrame, n: int) -> pd.DataFrame:
    df = df.sort_values("LapDistPct").copy()
    df["segment"] = (df["LapDistPct"] * n).astype(int).clip(0, n - 1)
    return df

def align_segments(s: pd.Series) -> pd.Series:
    return s.reindex(segments).ffill().bfill()

def brake_metrics_per_segment(df: pd.DataFrame, brake_threshold=BRAKE_THRESHOLD):
    avg_brake = df.groupby("segment")["Brake"].mean()
    brake_usage = (df["Brake"] > brake_threshold).groupby(df["segment"]).mean()
    return avg_brake, brake_usage

def throttle_metrics_per_segment(df: pd.DataFrame, throttle_threshold=THROTTLE_THRESHOLD):
    avg_throttle = df.groupby("segment")["Throttle"].mean()
    throttle_usage = (df["Throttle"] > throttle_threshold).groupby(df["segment"]).mean()
    return avg_throttle, throttle_usage

def estimate_segment_time(df: pd.DataFrame) -> pd.Series:
    dldp = df["LapDistPct"].diff().fillna(0).clip(lower=0)
    speed = df["Speed"].replace(0, pd.NA).ffill().bfill()
    dt = dldp / speed
    return dt.groupby(df["segment"]).sum()

# Prep
lap_fast = add_segments(lap_fast, num_segments)
lap_slow = add_segments(lap_slow, num_segments)

fast_time_seg = align_segments(estimate_segment_time(lap_fast))
slow_time_seg = align_segments(estimate_segment_time(lap_slow))

delta_time_ms = (slow_time_seg - fast_time_seg) * 1000  # relative units

# Brake
fast_avg_brake, fast_brake_usage = brake_metrics_per_segment(lap_fast)
slow_avg_brake, slow_brake_usage = brake_metrics_per_segment(lap_slow)

fast_avg_brake_pct = align_segments(fast_avg_brake) * 100
slow_avg_brake_pct = align_segments(slow_avg_brake) * 100
fast_brake_usage_pct = align_segments(fast_brake_usage) * 100
slow_brake_usage_pct = align_segments(slow_brake_usage) * 100

# Throttle usage (ignore avg throttle for now)
_, fast_throttle_usage = throttle_metrics_per_segment(lap_fast)
_, slow_throttle_usage = throttle_metrics_per_segment(lap_slow)
fast_throttle_usage_pct = align_segments(fast_throttle_usage) * 100
slow_throttle_usage_pct = align_segments(slow_throttle_usage) * 100

# Summary: worst loss + best gain
worst_segment = int(delta_time_ms.idxmax())
worst_value = float(delta_time_ms.max())
best_segment = int(delta_time_ms.idxmin())
best_value = float(delta_time_ms.min())

top3 = delta_time_ms.sort_values(ascending=False).head(3)

summary_lines = [
    f"Total (rel): {delta_time_ms.sum():.3f}",
    f"Worst loss: seg {worst_segment} (+{worst_value:.3f})",
    f"Best gain:  seg {best_segment} ({best_value:.3f})",
    "Top 3 loss seg:",
]
for seg, v in top3.items():
    summary_lines.append(f"  {int(seg)}: {v:.3f}")

summary_text = "\n".join(summary_lines)

# Plot
fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, sharex=True, figsize=(10, 9))

# Worst segment red line
for ax in (ax1, ax2, ax3, ax4):
    ax.axvline(worst_segment, linestyle="-", alpha=0.35, color="r")

# Time delta
ax1.plot(delta_time_ms.index, delta_time_ms.values)
ax1.set_ylabel("Time Δ (rel)")
ax1.set_title("Time Delta vs Inputs")

ax1.annotate(
    f"Worst loss\nSeg {worst_segment}\n+{worst_value:.3f}",
    xy=(worst_segment, worst_value),
    xytext=(worst_segment + 1.5, worst_value + 0.05),
    arrowprops=dict(arrowstyle="->", color="red", lw=1.5),
    bbox=dict(boxstyle="round", fc="white", ec="red", alpha=0.9),
    fontsize=9,
    color="red"
)

# Brake plots
ax2.plot(slow_avg_brake_pct.index, slow_avg_brake_pct.values, label="Slow")
ax2.plot(fast_avg_brake_pct.index, fast_avg_brake_pct.values, label="Fast")
ax2.set_ylabel("Avg Brake (%)")
ax2.legend()

ax3.plot(slow_brake_usage_pct.index, slow_brake_usage_pct.values, label="Slow")
ax3.plot(fast_brake_usage_pct.index, fast_brake_usage_pct.values, label="Fast")
ax3.set_ylabel("Brake Usage (%)")
ax3.legend()

# Throttle usage
ax4.plot(slow_throttle_usage_pct.index, slow_throttle_usage_pct.values, label="Slow")
ax4.plot(fast_throttle_usage_pct.index, fast_throttle_usage_pct.values, label="Fast")
ax4.set_ylabel("Throttle Usage (%)")
ax4.set_xlabel("Lap Segment")
ax4.set_title("On-throttle Time (Usage)")
ax4.legend()

# Summary box (top-right)
fig.text(
    0.99, 0.98, summary_text,
    ha="right", va="top",
    fontsize=9,
    bbox=dict(boxstyle="round", facecolor="white", alpha=0.85, edgecolor="gray")
)

# Cursor lines
cursor_lines = [ax.axvline(0, color="k", alpha=0.2, linestyle="--") for ax in (ax1, ax2, ax3, ax4)]

# Hover boxes per axis
hover_annots = {}
for ax in (ax1, ax2, ax3, ax4):
    ann = ax.annotate(
        "",
        xy=(0, 0),
        xytext=(10, 10),
        textcoords="offset points",
        bbox=dict(boxstyle="round", fc="white", ec="gray", alpha=0.9),
        fontsize=9,
        ha="left",
        va="bottom"
    )
    ann.set_visible(False)
    hover_annots[ax] = ann

last_x = {"val": None, "ax": None}

def on_move(event):
    if event.inaxes not in (ax1, ax2, ax3, ax4) or event.xdata is None:
        for ann in hover_annots.values():
            ann.set_visible(False)
        fig.canvas.draw_idle()
        return

    ax = event.inaxes
    x = int(round(event.xdata))
    x = max(0, min(num_segments - 1, x))

    if last_x["val"] == x and last_x["ax"] == ax:
        return
    last_x["val"] = x
    last_x["ax"] = ax

    for line in cursor_lines:
        line.set_xdata([x, x])

    tl = float(delta_time_ms.loc[x])
    ab_s = float(slow_avg_brake_pct.loc[x])
    ab_f = float(fast_avg_brake_pct.loc[x])
    bu_s = float(slow_brake_usage_pct.loc[x])
    bu_f = float(fast_brake_usage_pct.loc[x])
    tu_s = float(slow_throttle_usage_pct.loc[x])
    tu_f = float(fast_throttle_usage_pct.loc[x])

    tl_label = "Time gain" if tl < 0 else "Time loss"
    tl_val = abs(tl)

    text = (
        f"Seg {x}\n"
        f"{tl_label}: {tl_val:.3f}\n"
        f"Avg brake:  S {ab_s:.1f}% | F {ab_f:.1f}%\n"
        f"Brake use:  S {bu_s:.1f}% | F {bu_f:.1f}%\n"
        f"Thr use:    S {tu_s:.1f}% | F {tu_f:.1f}%"
    )

    for ann in hover_annots.values():
        ann.set_visible(False)

    ann = hover_annots[ax]
    ann.set_text(text)

    if ax is ax1:
        y = float(delta_time_ms.loc[x])
    elif ax is ax2:
        y = float(slow_avg_brake_pct.loc[x])
    elif ax is ax3:
        y = float(slow_brake_usage_pct.loc[x])
    else:
        y = float(slow_throttle_usage_pct.loc[x])

    ann.xy = (x, y)
    ann.set_position((-140, 10) if x > num_segments * 0.7 else (10, 10))
    ann.set_visible(True)

    fig.canvas.draw_idle()

fig.canvas.mpl_connect("motion_notify_event", on_move)

# integer ticks
for ax in (ax1, ax2, ax3, ax4):
    ax.set_xticks(range(num_segments))
    ax.set_xlim(-0.5, num_segments - 0.5)

plt.tight_layout()
plt.show()
