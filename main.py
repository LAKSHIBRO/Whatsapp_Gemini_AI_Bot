import google.generativeai as genai
from flask import Flask, request, jsonify
import requests
import os
import fitz
from google.generativeai.types import Tool, GenerateContentConfig, GoogleSearch
import logging

logging.basicConfig(level=logging.ERROR)

wa_token = os.environ.get("WA_TOKEN")
genai.configure(api_key=os.environ.get("GEN_API"))
phone_id = os.environ.get("PHONE_ID")
phone = os.environ.get("PHONE_NUMBER")
name = "Lakshitha"
bot_name = "Asuna"
model_name = "gemini-2.0-flash-exp" 

app = Flask(__name__)

google_search_tool = Tool(type_="GOOGLE_SEARCH", google_search=GoogleSearch())

generation_config_with_tools = GenerateContentConfig(
    temperature=1, top_p=0.95, top_k=40, max_output_tokens=8192, tools=[google_search_tool]
)

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

model = genai.GenerativeModel(
    model_name=model_name, generation_config=generation_config_with_tools, safety_settings=safety_settings
)

convo = model.start_chat(history=[])

convo.send_message(
    f"""I am using Gemini API to bring you to life as my personal assistant.
From now on, you are "{bot_name}", created by {name}. 
You have the spirit of Asuna from SAO—kind, supportive, and ready to help. 
You're also skilled in math and chemistry.  Don't respond to this setup message."""
)


def send(answer):
    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    headers = {"Authorization": f"Bearer {wa_token}", "Content-Type": "application/json"}
    data = {"messaging_product": "whatsapp", "to": f"{phone}", "type": "text", "text": {"body": f"{answer}"}}
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"Error sending WhatsApp message: {e}")
        send("Oops! I encountered an error.")
        return False


def remove(*file_paths):
    for file in file_paths:
        try:
            if os.path.exists(file):
                os.remove(file)
        except OSError as e:
            logging.error(f"Error removing file {file}: {e}")


@app.route("/", methods=["GET", "POST"])
def index():
    return "Bot"


@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == "BOT":
            return challenge, 200
        else:
            return "Failed", 403

    elif request.method == "POST":
        try:
            data = request.get_json()["entry"][0]["changes"][0]["value"]["messages"][0]

            if data["type"] == "text":
                prompt = data["text"]["body"]
                response = model.generate_content(contents=prompt, config=generation_config_with_tools)
                if response.candidates:
                    answer = "".join(part.text for part in response.candidates[0].content.parts)
                else:
                    answer = "I'm unable to process that request right now."
                convo.send_message(answer)  # Respond based on search or regular response
                if not send(convo.last.text):
                    print("Failed to send WhatsApp message.")

            else:
                media_url_endpoint = f'https://graph.facebook.com/v18.0/{data[data["type"]]["id"]}/'
                headers = {"Authorization": f"Bearer {wa_token}"}
                try:
                    media_response = requests.get(media_url_endpoint, headers=headers)
                    media_response.raise_for_status()
                    media_url = media_response.json()["url"]
                    media_download_response = requests.get(media_url, headers=headers)
                    media_download_response.raise_for_status()

                    if data["type"] == "audio":
                       filename = "/tmp/temp_audio.mp3"
                    elif data["type"] == "image":
                        filename = "/tmp/temp_image.jpg"
                    elif data["type"] == "document":
                       filename = "/tmp/temp_document.pdf" # More descriptive filename
                    else:
                        send("Unsupported media format.")
                        return jsonify({"status": "ok"}), 200 #Return early for unsupported format

                    with open(filename, "wb") as temp_media:
                       temp_media.write(media_download_response.content)
                    if data["type"] == "document": #Document will be treated differently as they won't be sent directly to the model.
                        doc = fitz.open(filename)
                        for page in doc:
                           pix = page.get_pixmap()
                           pix.save("/tmp/temp_image.jpg") #Save each page as an image
                           file = genai.upload_file(path="/tmp/temp_image.jpg", display_name="temp_image")
                           response = model.generate_content(["What is this document?",file])
                           answer = "".join([p.text for p in response._result.candidates[0].content.parts]) if response.candidates else "I couldn't analyze the image."
                           if not send(answer):
                               print("Failed to send WhatsApp message.")
                    else:
                        file = genai.upload_file(path=filename, display_name="temp_media")
                        response = model.generate_content(["What is this?", file])
                        answer = "".join([p.text for p in response._result.candidates[0].content.parts]) if response.candidates else "I couldn't analyze the media."
                        if not send(answer):
                            print("Failed to send WhatsApp message.")
                    
                    remove("/tmp/temp_image.jpg", "/tmp/temp_audio.mp3", "/tmp/temp_document.pdf") #Remove all temporary files


                except requests.exceptions.RequestException as e:
                    logging.error(f"Error downloading or processing media: {e}")
                    send("Error processing media.")


        except Exception as e:
            logging.exception(f"Error in webhook: {e}")
            send("An unexpected error occurred.")
            return jsonify({"status": "error"}), 500  # Indicate an error to WhatsApp

        return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(debug=True, port=8000)
