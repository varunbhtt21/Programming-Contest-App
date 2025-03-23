import os
import sys

# Add the src directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

# Run the Streamlit app
os.system("streamlit run src/app.py") 