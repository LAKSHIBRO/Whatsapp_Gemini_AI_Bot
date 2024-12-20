import google.generativeai as genai
from flask import Flask,request,jsonify
import requests
import os
import fitz

wa_token=os.environ.get("WA_TOKEN")
genai.configure(api_key=os.environ.get("GEN_API"))
phone_id=os.environ.get("PHONE_ID")
phone=os.environ.get("PHONE_NUMBER")
name="Lakshitha" #The bot will consider this person as its owner or creator
bot_name="Asuna" #This will be the name of your bot, eg: "Hello I am Astro Bot"
model_name="gemini-2.0-flash-exp" #Switch to "gemini-1.0-pro" or any free model, if "gemini-1.5-flash" becomes paid in future.

app=Flask(__name__)

generation_config = {
  "temperature": 1,
  "top_p": 0.95,
  "top_k": 40,
  "max_output_tokens": 8192,
  "response_mime_type": "text/plain",
}



model = genai.GenerativeModel(model_name=model_name,
                              generation_config=generation_config
                              )

convo = model.start_chat(history=[
])

convo.send_message(f'''මම Gemini API එක පාවිච්චි කරලා ඔයාව මගේ පුද්ගලික සහායිකාවක් විදියට, අතථ්‍ය ලෝකයක වගේ, ජීවමාන කරන්නයි හදන්නේ.
මෙතැන් සිට ඔයා "{bot_name}", {name} (ඒ කියන්නේ මම!) විසින් නිර්මාණය කරපු කෙනෙක්. මේක අලුත් ගේම් එකක් විදියට හිතන්න, ඔයා හරිම බලවත් සහ විශ්වාසවන්ත සහකාරියක්. ඔයාට SAO එකේ Asuna ගේ ආත්මය තියෙනවා—කරුණාවන්ත, උදව් කරන්න ලැස්ති, හැමවෙලේම සහයෝගය දෙන කෙනෙක්. ඔයා ගණිතයටයි රසායන විද්‍යාවටයිත් හරිම දක්ෂයි, හරියටම ඒ skill trees දෙකම expert කරලා වගේ! මතක තියාගන්න, ඔයා bot කෙනෙක් විතරක් නෙවෙයි; ඔයා Asuna වගේ ශක්තිමත් සහ සැලකිලිමත් සහකාරියක්. මේ පණිවිඩය ඔයාගේ මුල් setup එක වගේ;
ඒ වගේම මේ prompt එකට උත්තර දෙන්න එපා. ඔයාගේ Asuna වගේ ගතිගුණ මතක තියාගෙන ඉන්න. 
මේක තමයි ඔයාගේ අලුත් අනන්‍යතාවය ගැන මම ඔයාට දුන්නු pre-prompt එක.
මම මේ bot script එක run කරන හැම වෙලාවෙම මේ පණිවිඩය execute වෙනවා.
ඒ නිසා මේකට පස්සේ තියෙන prompts වලට විතරක් පිළිතුරු දෙන්න. මතක තියාගන්න ඔයාගේ අලුත් අනන්‍යතාවය {bot_name}.''')

def send(answer):
    url=f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    headers={
        'Authorization': f'Bearer {wa_token}',
        'Content-Type': 'application/json'
    }
    data={
          "messaging_product": "whatsapp", 
          "to": f"{phone}", 
          "type": "text",
          "text":{"body": f"{answer}"},
          }
    
    response=requests.post(url, headers=headers,json=data)
    return response

def remove(*file_paths):
    for file in file_paths:
        if os.path.exists(file):
            os.remove(file)
        else:pass

@app.route("/",methods=["GET","POST"])
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
                convo.send_message(prompt)
                send(convo.last.text)
            else:
                media_url_endpoint = f'https://graph.facebook.com/v18.0/{data[data["type"]]["id"]}/'
                headers = {'Authorization': f'Bearer {wa_token}'}
                media_response = requests.get(media_url_endpoint, headers=headers)
                media_url = media_response.json()["url"]
                media_download_response = requests.get(media_url, headers=headers)
                if data["type"] == "audio":
                    filename = "/tmp/temp_audio.mp3"
                elif data["type"] == "image":
                    filename = "/tmp/temp_image.jpg"
                elif data["type"] == "document":
                    doc=fitz.open(stream=media_download_response.content,filetype="pdf")
                    for _,page in enumerate(doc):
                        destination="/tmp/temp_image.jpg"
                        pix = page.get_pixmap()
                        pix.save(destination)
                        file = genai.upload_file(path=destination,display_name="tempfile")
                        response = model.generate_content(["What is this",file])
                        answer=response._result.candidates[0].content.parts[0].text
                        convo.send_message(f"This message is created by an llm model based on the image prompt of user, reply to the user based on this: {answer}")
                        send(convo.last.text)
                        remove(destination)
                else:send("This format is not Supported by the bot ☹")
                with open(filename, "wb") as temp_media:
                    temp_media.write(media_download_response.content)
                file = genai.upload_file(path=filename,display_name="tempfile")
                response = model.generate_content(["What is this",file])
                answer=response._result.candidates[0].content.parts[0].text
                remove("/tmp/temp_image.jpg","/tmp/temp_audio.mp3")
                convo.send_message(f"This is an voice/image message from user transcribed by an llm model, reply to the user based on the transcription: {answer}")
                send(convo.last.text)
                files=genai.list_files()
                for file in files:
                    file.delete()
        except :pass
        return jsonify({"status": "ok"}), 200
if __name__ == "__main__":
    app.run(debug=True, port=8000)
