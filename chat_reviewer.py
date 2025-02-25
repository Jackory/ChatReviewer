import numpy as np
import os
import re
import datetime
import time
import openai, tenacity
import argparse
import configparser
import json
import tiktoken
from get_paper_from_pdf import Paper

# 定义Reviewer类
class Reviewer:
    # 初始化方法，设置属性
    def __init__(self, args=None):
        if args.language == 'en':
            self.language = 'English'
        elif args.language == 'zh':
            self.language = 'Chinese'
        else:
            self.language = 'Chinese'        
        # 创建一个ConfigParser对象
        self.config = configparser.ConfigParser()
        # 读取配置文件
        self.config.read('apikey.ini')
        # 获取某个键对应的值        
        self.chat_api_list = self.config.get('OpenAI', 'OPENAI_API_KEYS')[1:-1].replace('\'', '').split(',')
        self.chat_api_list = [api.strip() for api in self.chat_api_list if len(api) > 5]
        self.cur_api = 0
        self.file_format = args.file_format        
        self.max_token_num = 4096
        self.encoding = tiktoken.get_encoding("gpt2")
    
    def validateTitle(self, title):
        # 修正论文的路径格式
        rstr = r"[\/\\\:\*\?\"\<\>\|]" # '/ \ : * ? " < > |'
        new_title = re.sub(rstr, "_", title) # 替换为下划线
        return new_title


    def review_by_chatgpt(self, paper_list):
        htmls = []
        for paper_index, paper in enumerate(paper_list):
            # 提取重要的论文内容
            text = ''
            text += 'Title:' + paper.title
            text += list(paper.section_text_dict.values())[0]
            text += 'Introduction:' + paper.section_text_dict['Introduction']
            text += list(paper.section_text_dict.values())[4]
            text += list(paper.section_text_dict.values())[5]
            try:
                text += 'Conclusion:' + paper.section_text_dict['Conclusion']
            except:
                pass
            chat_review_text = self.chat_review(text=text)            
            htmls.append('## Paper:' + str(paper_index+1))
            htmls.append('\n\n\n')            
            htmls.append(chat_review_text)
            
            # 将审稿意见保存起来
            date_str = str(datetime.datetime.now())[:13].replace(' ', '-')
            try:
                export_path = os.path.join('./', 'output_file')
                os.makedirs(export_path)
            except:
                pass                             
            mode = 'w' if paper_index == 0 else 'a'
            file_name = os.path.join(export_path, date_str+'-'+self.validateTitle(paper.title)+"."+self.file_format)
            self.export_to_markdown("\n".join(htmls), file_name=file_name, mode=mode)
            htmls = [] 
    
    
    @tenacity.retry(wait=tenacity.wait_exponential(multiplier=1, min=4, max=10),
                    stop=tenacity.stop_after_attempt(5),
                    reraise=True)
    def chat_review(self, text):
        openai.api_key = self.chat_api_list[self.cur_api]
        self.cur_api += 1
        self.cur_api = 0 if self.cur_api >= len(self.chat_api_list)-1 else self.cur_api
        review_prompt_token = 1000        
        text_token = len(self.encoding.encode(text))
        input_text_index = int(len(text)*(self.max_token_num-review_prompt_token)/text_token)
        input_text = "This is the paper for your review:" + text[:input_text_index]
        with open('ReviewFormat.txt', 'r') as file:   # 读取特定的审稿格式
            review_format = file.read()
        messages=[
                {"role": "system", "content": "You are a professional reviewer in the field of "+args.research_fields+". Now I will give you a paper. You need to give a complete review opinion according to the following requirements and format:"+ review_format +" Please answer in {}.".format(self.language)},
                {"role": "user", "content": input_text},
            ]
                
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
        )
        result = ''
        for choice in response.choices:
            result += choice.message.content
        print("********"*10)
        print(result)
        print("********"*10)
        print("prompt_token_used:", response.usage.prompt_tokens)
        print("completion_token_used:", response.usage.completion_tokens)
        print("total_token_used:", response.usage.total_tokens)
        print("response_time:", response.response_ms/1000.0, 's')                    
        return result        
                        
    def export_to_markdown(self, text, file_name, mode='w'):
        # 使用markdown模块的convert方法，将文本转换为html格式
        # html = markdown.markdown(text)
        # 打开一个文件，以写入模式
        with open(file_name, mode, encoding="utf-8") as f:
            # 将html格式的内容写入文件
            f.write(text)                    

def main(args):            

    reviewer1 = Reviewer(args=args)
    # 开始判断是路径还是文件：   
    paper_list = []     
    if args.paper_path.endswith(".pdf"):
        paper_list.append(Paper(path=args.paper_path))            
    else:
        for root, dirs, files in os.walk(args.paper_path):
            print("root:", root, "dirs:", dirs, 'files:', files) #当前目录路径
            for filename in files:
                # 如果找到PDF文件，则将其复制到目标文件夹中
                if filename.endswith(".pdf"):
                    paper_list.append(Paper(path=os.path.join(root, filename)))        
    print("------------------paper_num: {}------------------".format(len(paper_list)))        
    [print(paper_index, paper_name.path.split('\\')[-1]) for paper_index, paper_name in enumerate(paper_list)]
    reviewer1.review_by_chatgpt(paper_list=paper_list)

    
    
if __name__ == '__main__':    
    parser = argparse.ArgumentParser()
    parser.add_argument("--paper_path", type=str, default='', help="path of papers")
    parser.add_argument("--file_format", type=str, default='txt', help="output file format")
    parser.add_argument("--research_fields", type=str, default='computer science and artificial intelligence', help="the research fields of paper")
    parser.add_argument("--language", type=str, default='en', help="output lauguage, en or zh")
    
    args = parser.parse_args()
    start_time = time.time()
    main(args=args)    
    print("review time:", time.time() - start_time)
    
