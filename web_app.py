import os
import asyncio
import threading
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import PyPDF2
import json

from agents.job_agent import run_linkedin_agent

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Global state to track bot status
bot_status = {
    "is_running": False,
    "message": "Waiting to start...",
    "applications": 0,
    "stop_requested": False,
    "applied_companies": []
}

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"Error reading PDF: {e}")
    return text

def run_agent_in_thread(keyword, location, resume_text, experience, extra_details):
    global bot_status
    bot_status["is_running"] = True
    bot_status["message"] = "Initializing agent..."
    bot_status["applications"] = 0
    bot_status["stop_requested"] = False
    bot_status["applied_companies"] = []
    
    try:
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run the agent
        loop.run_until_complete(
            run_linkedin_agent(
                keyword=keyword,
                location=location,
                resume_text=resume_text,
                experience=experience,
                extra_details=extra_details,
                status_dict=bot_status
            )
        )
        if not bot_status.get("stop_requested"):
            bot_status["message"] = "Completed successfully!"
    except Exception as e:
        if not bot_status.get("stop_requested"):
            bot_status["message"] = f"Error: {str(e)}"
        print(f"Agent error: {e}")
    finally:
        bot_status["is_running"] = False
        try:
            loop.close()
        except:
            pass

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify(bot_status)

@app.route('/api/stop', methods=['POST'])
def stop_bot():
    global bot_status
    if bot_status["is_running"]:
        bot_status["stop_requested"] = True
        bot_status["message"] = "Stopping bot..."
        return jsonify({"message": "Stop signal sent to bot"})
    return jsonify({"message": "Bot is not running"}), 400

@app.route('/api/start', methods=['POST'])
def start_bot():
    global bot_status
    
    if bot_status["is_running"]:
        return jsonify({"error": "Bot is already running"}), 400

    # Get form data
    keyword = request.form.get('keyword', 'Python Developer')
    location = request.form.get('location', 'Chennai')
    experience = request.form.get('experience', '0')
    extra_details = request.form.get('extra_details', '')

    # Handle file upload
    resume_text = ""
    if 'resume' in request.files:
        file = request.files['resume']
        if file.filename != '':
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            resume_text = extract_text_from_pdf(filepath)

    # Start thread
    thread = threading.Thread(
        target=run_agent_in_thread,
        args=(keyword, location, resume_text, experience, extra_details)
    )
    thread.daemon = True
    thread.start()

    return jsonify({"message": "Bot started successfully"})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
