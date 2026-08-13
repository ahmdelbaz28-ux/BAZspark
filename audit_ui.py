import os
import re

BACKEND_DIRS = ['backend', 'fireai']
FRONTEND_DIR = 'frontend/src'

# Regex to find @app.get("/path") or @router.post('/path')
ROUTE_REGEX = re.compile(r'@(?:app|router)\.(get|post|put|delete|patch|websocket)\s*\(\s*[\'"]([^\'"]+)[\'"]')

def get_all_routes():
    routes = []
    for d in BACKEND_DIRS:
        for root, _, files in os.walk(d):
            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    with open(filepath, encoding='utf-8') as f:
                        for line in f:
                            match = ROUTE_REGEX.search(line)
                            if match:
                                method = match.group(1).upper()
                                path = match.group(2)
                                routes.append((method, path, filepath))
    return routes

if __name__ == "__main__":
    routes = get_all_routes()

    # We will search the frontend files for substrings of the paths
    unmapped = []
    mapped = []

    # Pre-read all frontend code to speed up searching
    frontend_code = ""
    for root, _, files in os.walk(FRONTEND_DIR):
        for file in files:
            if file.endswith(('.ts', '.tsx', '.js', '.jsx')):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, encoding='utf-8') as f:
                        frontend_code += f.read() + "\n"
                except Exception:
                    pass

    for method, path, filepath in routes:
        # Convert path /api/v1/monitor/health to search terms
        search_path = re.sub(r'\{[^}]+\}', '', path) # remove path params
        parts = [p for p in search_path.split('/') if p]

        is_mapped = False
        if len(parts) > 0:
            search_str = "/".join(parts)
            if search_str in frontend_code or (len(parts) >= 2 and "/".join(parts[-2:]) in frontend_code) or (len(parts) == 1 and f"/{parts[0]}" in frontend_code):
                is_mapped = True

        if is_mapped:
            mapped.append((method, path, filepath))
        else:
            unmapped.append((method, path, filepath))

    # Output markdown report
    with open('ui_coverage_report.md', 'w', encoding='utf-8') as f:
        f.write("# UI Coverage Report\n\n")
        f.write(f"Total Backend Features (Endpoints): {len(routes)}\n")
        f.write(f"Total Mapped Features: {len(mapped)}\n")
        f.write(f"Total Missing UI Features: {len(unmapped)}\n")
        if len(routes) > 0:
            f.write(f"Coverage Percentage: {(len(mapped)/len(routes))*100:.2f}%\n\n")

        f.write("## ❌ Missing UI Coverage (Orphan Backend Endpoints)\n\n")
        f.write("| Method | Endpoint | Backend Location |\n")
        f.write("|--------|----------|------------------|\n")
        for m, p, loc in sorted(unmapped, key=lambda x: x[1]):
            f.write(f"| {m} | `{p}` | {loc} |\n")

        f.write("\n## ✅ Mapped Features\n\n")
        f.write("| Method | Endpoint | Backend Location |\n")
        f.write("|--------|----------|------------------|\n")
        for m, p, loc in sorted(mapped, key=lambda x: x[1]):
            f.write(f"| {m} | `{p}` | {loc} |\n")
