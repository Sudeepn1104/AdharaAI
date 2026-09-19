import pandas as pd
import zlib
import base64

df = pd.read_csv("adharaai_deployment_ready.csv")

# Create a beautiful HTML string
html = f"""
<!DOCTYPE html>
<html>
<head>
<title>AdharaAI Dataset</title>
<style>
    body {{ font-family: Arial, sans-serif; margin: 20px; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
    th, td {{ border: 1px solid #dddddd; text-align: left; padding: 8px; }}
    th {{ background-color: #f2f2f2; position: sticky; top: 0; }}
    tr:nth-child(even) {{ background-color: #f9f9f9; }}
    .high {{ background-color: #ffe6e6; color: #cc0000; font-weight: bold; }}
    .medium {{ background-color: #fff2e6; color: #cc7a00; font-weight: bold; }}
    .low {{ background-color: #e6ffe6; color: #008000; font-weight: bold; }}
</style>
</head>
<body>
    <h2>AdharaAI Deployment Ready Dataset (111 Rows)</h2>
    <table>
        <tr>
            <th>Row</th>
            <th>Clause Text</th>
            <th>Risk Level</th>
            <th>Clause Type</th>
            <th>Risk Reason</th>
            <th>Simplified Text</th>
            <th>Tip</th>
            <th>Source File</th>
        </tr>
"""

for idx, row in df.iterrows():
    risk_class = row['risk_level'].lower()
    html += f"""
        <tr>
            <td>{idx}</td>
            <td>{row['clause_text']}</td>
            <td class="{risk_class}">{row['risk_level']}</td>
            <td>{row['clause_type']}</td>
            <td>{row['risk_reason']}</td>
            <td>{row['simplified_text']}</td>
            <td>{row['tip']}</td>
            <td>{row['source_file']}</td>
        </tr>
    """

html += """
    </table>
</body>
</html>
"""

# Compress and encode
compressed = zlib.compress(html.encode('utf-8'))
b64_str = base64.b64encode(compressed).decode('utf-8')

chunks = [b64_str[i:i+80] for i in range(0, len(b64_str), 80)]
chunk_formatted = ",\n        ".join([f'"{c}"' for c in chunks])

script = f"""import os
import zlib
import base64

def build_pdf_view():
    payload_chunks = [
        {chunk_formatted}
    ]
    
    payload = "".join(payload_chunks)
    
    try:
        html_bytes = zlib.decompress(base64.b64decode(payload))
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        output_file = os.path.join(desktop_path, "AdharaAI_Dataset_View.html")
        
        with open(output_file, "wb") as f:
            f.write(html_bytes)
            
        print("✅ SUCCESS!")
        print(f"✅ An HTML document has been saved directly to your Desktop: {{output_file}}")
        print("✅ Double-click it to open it in Chrome/Edge, then press Ctrl+P to save it as a PDF!")
        
    except Exception as e:
        print(f"❌ ERROR: {{e}}")

if __name__ == "__main__":
    build_pdf_view()
"""

with open("generate_html_script.py", "w") as f:
    f.write(script)
print("HTML script prepared.")