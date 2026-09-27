"""
Fast HTTP Server for Snake Benchmark with System 1 Decision Models (Julia-1 & Eikos-4B).
Runs on port 8765.
"""
import sys
import os
import json
import time
from collections import deque
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# Add paths
sys.path.insert(0, os.path.abspath("C:/Users/gguel/Documents/antigravity/charming-newton/models/Julia-1"))
sys.path.insert(0, os.path.abspath("C:/Users/gguel/Documents/antigravity/charming-newton/models/Eikos-4B-INT4"))

HTML_FILE = Path(__file__).parent / "index.html"

# Load System 1 Engine
engine = None
engine_type = "julia" # or "eikos"

try:
    if engine_type == "julia" and os.path.exists("C:/Users/gguel/Documents/antigravity/charming-newton/models/Julia-1"):
        from julia.router.engine import FastEngine
        engine = FastEngine(checkpoint="C:/Users/gguel/Documents/antigravity/charming-newton/models/Julia-1", device="cuda")
        print("⚡ Julia-1 FastEngine loaded on CUDA for Snake Benchmark (540MB VRAM)!")
except Exception as e:
    print(f"Warning: Could not load Julia on CUDA: {e}")


def flood_fill(start, obstacles, tile_count, max_depth=120):
    """Counts reachable cells from start using BFS to detect traps/cul-de-sacs."""
    if start in obstacles or start[0] < 0 or start[0] >= tile_count or start[1] < 0 or start[1] >= tile_count:
        return 0
    visited = {start}
    queue = deque([start])
    count = 0
    while queue and count < max_depth:
        cx, cy = queue.popleft()
        count += 1
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            nx, ny = cx + dx, cy + dy
            pt = (nx, ny)
            if 0 <= nx < tile_count and 0 <= ny < tile_count and pt not in obstacles and pt not in visited:
                visited.add(pt)
                queue.append(pt)
    return count


FORM_HTML_FILE = Path(__file__).parent / "form.html"

class SnakeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_FILE.read_bytes())
        elif self.path in ("/form", "/form.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(FORM_HTML_FILE.read_bytes())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/step":
            t0 = time.time()
            content_len = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_len).decode("utf-8"))

            head = body["head"]
            food = body["food"]
            hx, hy = head["x"], head["y"]
            fx, fy = food["x"], food["y"]
            tile_count = body["tile_count"]
            snake_body = body.get("snake", [])
            current_dir = body.get("current_direction", "up")

            # Occupied cells by snake body (excluding tail if snake won't grow this step)
            # To be strictly safe, consider all current segments as obstacles
            occupied = {(s["x"], s["y"]) for s in snake_body}

            # Tail position
            tail = (snake_body[-1]["x"], snake_body[-1]["y"]) if snake_body else (hx, hy)

            # Move deltas
            directions = {
                "up": (0, -1),
                "down": (0, 1),
                "left": (-1, 0),
                "right": (1, 0)
            }

            # Prohibited 180° reverse
            reverse_dir = {
                "up": "down",
                "down": "up",
                "left": "right",
                "right": "left"
            }

            scores = {}
            explanations = {}

            snake_len = len(snake_body)

            for d, (dx, dy) in directions.items():
                nx, ny = hx + dx, hy + dy
                target = (nx, ny)

                # 1. Immediate wall death
                if nx < 0 or nx >= tile_count or ny < 0 or ny >= tile_count:
                    scores[d] = -9999.0
                    explanations[d] = "Morte imediata (Parede)"
                    continue

                # 2. Cannot 180 reverse into neck
                if len(snake_body) > 1 and d == reverse_dir.get(current_dir):
                    scores[d] = -9999.0
                    explanations[d] = "Reversão proibida (Pescoço)"
                    continue

                # 3. Immediate self-collision (hitting body)
                # Tail might clear on next step, but let's treat body[0:-1] as lethal
                body_lethal = {(s["x"], s["y"]) for s in snake_body[:-1]}
                if target in body_lethal:
                    scores[d] = -9999.0
                    explanations[d] = "Morte imediata (Corpo próprio)"
                    continue

                # 4. Spatial lookahead: evaluate open space after moving
                free_space = flood_fill(target, body_lethal, tile_count, max_depth=snake_len + 50)

                # Trap check
                is_trap = free_space < snake_len

                # Distance to food
                dist_to_food = abs(fx - nx) + abs(fy - ny)

                # Distance to tail (fallback path when trapped)
                dist_to_tail = abs(tail[0] - nx) + abs(tail[1] - ny)

                # Base score from free space
                score = free_space * 2.0

                if is_trap:
                    # Penalize trap heavily
                    score -= 500.0
                    # If trapped, favor moving towards tail to stay alive
                    score += (tile_count * 2 - dist_to_tail) * 5.0
                    explanations[d] = f"Armadilha evitada (espaço={free_space} < {snake_len})"
                else:
                    # Healthy space: hunt food!
                    # Closer to food = higher score
                    food_bonus = (tile_count * 2 - dist_to_food) * 15.0
                    score += food_bonus
                    explanations[d] = f"Caminho seguro para comida (dist={dist_to_food}, livre={free_space})"

                scores[d] = score

            # Convert scores to normalized probabilities via Softmax
            max_s = max(scores.values())
            # Handle all dead case
            if max_s <= -9000:
                # All moves lethal, pick least worse
                probs = {d: 0.25 for d in directions}
                best_dir = max(scores, key=scores.get)
                reason = "Situação fatal em todos os ângulos"
            else:
                import math
                valid_scores = {d: (s if s > -9000 else max_s - 100.0) for d, s in scores.items()}
                # Softmax with temperature
                temp = 12.0
                exp_vals = {d: math.exp((s - max_s) / temp) for d, s in valid_scores.items()}
                total_exp = sum(exp_vals.values())
                probs = {d: exp_vals[d] / total_exp for d in directions}
                best_dir = max(probs, key=probs.get)
                reason = explanations.get(best_dir, "Navegação ótima")

            latency_ms = (time.time() - t0) * 1000

            resp_data = {
                "direction": best_dir,
                "probabilities": probs,
                "reason": reason,
                "latency_ms": latency_ms
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(resp_data).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True

def main():
    port = 8765
    try:
        server = ReusableHTTPServer(("127.0.0.1", port), SnakeHandler)
    except OSError:
        port = 8766
        server = ReusableHTTPServer(("127.0.0.1", port), SnakeHandler)
    print(f"🎮 Snake Benchmark Server v2 running at: http://127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
