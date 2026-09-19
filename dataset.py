import pandas as pd
import zlib
import base64

# Read the full 111-row dataset we made earlier
df = pd.read_csv("adharaai_deployment_ready.csv")
csv_text = df.to_csv(index=False)

# Compress and encode
compressed = zlib.compress(csv_text.encode('utf-8'))
b64_str = base64.b64encode(compressed).decode('utf-8')

# Chunk into 80 character lines
chunks = [b64_str[i:i+80] for i in range(0, len(b64_str), 80)]
chunk_formatted = ",\n        ".join([f'"{c}"' for c in chunks])

script = f"""import os
import zlib
import base64

def build_dataset():
    # Base64 encoded, compressed CSV data (all 111 rows)
    payload_chunks = [
        {chunk_formatted}
    ]
    
    payload = "".join(payload_chunks)
    
    try:
        # Decode and decompress
        csv_bytes = zlib.decompress(base64.b64decode(payload))
        
        # Write directly to the Desktop to guarantee you can find it
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        output_file = os.path.join(desktop_path, "adharaai_deployment_ready.csv")
        
        with open(output_file, "wb") as f:
            f.write(csv_bytes)
            
        print("✅ SUCCESS!")
        print(f"✅ File saved exactly here: {{output_file}}")
        print("✅ You can now close this terminal and look on your Desktop screen.")
        
    except Exception as e:
        print(f"❌ ERROR: {{e}}")

if __name__ == "__main__":
    build_dataset()
"""

print(f"Script length: {len(script)}")
# Just write it to a file so we know it works
with open("final_build_script.py", "w") as f:
    f.write(script)