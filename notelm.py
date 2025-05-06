import os
import argparse
import requests
from pathlib import Path
from pypdf import PdfReader
from typing import List
import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer
from dotenv import load_dotenv
import time
from pydub import AudioSegment
from prompt import DEFAULT_PROMPT, DISCUSSION_PROMPT, TEACHING_PROMPT, ARGUMENT_PROMPT, INTERVIEW_PROMPT

os.environ["PATH"] += os.pathsep + "/usr/bin"  
AudioSegment.ffmpeg = "/usr/bin/ffmpeg"  

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")

class DialogueItem:
    def __init__(self, speaker: str, text: str):
        self.speaker = speaker
        self.text = text

class PodcastGenerator:
    def __init__(self):
        self.host_voice = "loongstella"
        self.guest_voice = "longshu"
        self.max_retries = 3
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        
        try:
            with open(pdf_path, "rb") as f:
                reader = PdfReader(f)
                return "\n\n".join([page.extract_text() for page in reader.pages])
        except Exception as e:
            raise RuntimeError(f"PDF解析失败: {str(e)}")

    def generate_dialogue(self, text: str,prompt_type: str,len:str,minutes:str,count:str) -> List[DialogueItem]:
        
        if prompt_type == "discussion":
            prompt = DISCUSSION_PROMPT
        elif prompt_type == "teaching":
            prompt = TEACHING_PROMPT
        elif prompt_type == "argument":
            prompt = ARGUMENT_PROMPT
        elif prompt_type == "interview":
            prompt = INTERVIEW_PROMPT
        else:
            prompt = DEFAULT_PROMPT  # 默认的prompt
        headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
        prompt = prompt.replace("{text}", text)
        prompt = prompt.replace("{len}", len)
        prompt = prompt.replace("{minutes}", minutes)
        prompt = prompt.replace("{count}", count)
        # print(prompt)

        payload = {
            "model": "deepseek-chat",
            # "model":'deepseek-reasoner',
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 5000
        }
        
        for attempt in range(self.max_retries):
            try:
                response = requests.post(DEEPSEEK_API_URL, json=payload, headers=headers)
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                return self._parse_dialogue(content)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise RuntimeError(f"对话生成失败: {str(e)}")
                time.sleep(2**attempt)
    def _parse_dialogue(self, text: str) -> List[DialogueItem]:
        """"""
        dialogues = []
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("[主持人]"):
                dialogues.append(DialogueItem("Host", line[5:].strip()))
            elif line.startswith("[嘉宾]"):
                dialogues.append(DialogueItem("Guest", line[4:].strip()))
            else:
                print(f"忽略无法解析的行: {line}")
        return dialogues

    def print_dialogue(self, dialogues: List[DialogueItem]):
        
        print("\n生成的对话内容：")
        for idx, d in enumerate(dialogues, 1):
            print(f"[{idx}] {d.speaker}: {d.text}")
    #合成音频
    def synthesize_audio(self, dialogues: List[DialogueItem], output_path: str):
        
        if not dialogues:
            raise ValueError("没有可合成的对话内容")
        
        combined_audio = AudioSegment.silent(duration=0)
        
        for idx, dialogue in enumerate(dialogues):
            voice = self.host_voice if dialogue.speaker == "Host" else self.guest_voice
            audio_file = f"temp_{idx}.mp3"
            
            try:
                
                synthesizer = SpeechSynthesizer(
                    model="cosyvoice-v1",
                    voice=voice,
                    callback=None
                    
                )
                audio_data = synthesizer.call(dialogue.text)
                
                
                with open(audio_file, "wb") as f:
                    f.write(audio_data)
                
                
                segment = AudioSegment.from_file(audio_file)
                if idx > 0:
                    combined_audio += AudioSegment.silent(duration=500)
                combined_audio += segment
                
                os.remove(audio_file)
                
            except Exception as e:
                raise RuntimeError(f"语音合成失败（第{idx+1}段）: {str(e)}")
        
        combined_audio.export(output_path, format="mp3")

def main():
    parser = argparse.ArgumentParser(description="PDF转播客工具")
    parser.add_argument("--input", required=True, help="输入PDF文件路径")
    parser.add_argument("--output_dir", default="./output", help="输出目录")
    parser.add_argument("--prompt_type", default="default", choices=["default", "discussion", "teaching", "argument", "interview"], help="选择使用的prompt类型")
    parser.add_argument("--len", default="100", help="每段对话长度")
    parser.add_argument("--minutes", default="3", help="生成对话的时长(分钟)")
    parser.add_argument("--count", default="25", help="对话次数")
    args = parser.parse_args()

    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    
    generator = PodcastGenerator()
    
    try:
        
        print("\n[1/3] 正在解析PDF...")
        text = generator.extract_text_from_pdf(args.input)
        print(f"提取到 {len(text)} 字符")
        
        
        print("\n[2/3] 生成对话中...")
        # dialogues = generator.generate_dialogue(text,args.prompt_type)
        
        dialogues = generator.generate_dialogue(text,args.prompt_type,args.len,args.minutes,args.count)
        generator.print_dialogue(dialogues)  
        
        
        print("\n[3/3] 合成音频中...")
        output_path = os.path.join(args.output_dir, "podcast.mp3")
        generator.synthesize_audio(dialogues, output_path)
        
        
        transcript_path = os.path.join(args.output_dir, "transcript.txt")
        with open(transcript_path, "w") as f:
            for d in dialogues:
                f.write(f"{d.speaker}: {d.text}\n")
        
        print(f"\n处理完成！\n音频文件: {output_path}\n文字稿: {transcript_path}")
        
    except Exception as e:
        print(f"\n处理失败: {str(e)}")

if __name__ == "__main__":
    main()
    
