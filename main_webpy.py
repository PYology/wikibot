# encoding: utf-8
import re
import urllib
import urllib2
import json
import sys 
import time
import BeautifulSoup
import web
import logging

reload(sys) 
sys.setdefaultencoding('utf8') 

lang = 'en'
reply = {
	'feedback':'Thanks for your feedback!',
	'language-code-err':'Hmm, the language you input is not supported by wikipedia.',
	'language-404':'Hmm, the topic is not available in the languange you specify. Showing results in the original language.',
	'detectLang-err':'Detect Langage Usage is up. Can only process English request. Donate!',
	'search':'No such page. Try search instead.'
}

def convert(s):
    try:
        return s.group(0).encode('latin1').decode('utf8')
    except:
        return s.group(0)

def fetch(url):
	# fetch content of any url request
	request = urllib2.Request(url)
	request.add_header('User-Agent', 'Wiki for WeChat, http://mp.weixin.qq.com')
	result = urllib2.urlopen(request)
	content = result.read()
	return content

def generate_url(message,lang = 'en'):

	urlDict = {
		'article_json': 'http://%s.wikipedia.org/w/api.php?action=query&titles=%s&prop=revisions&rvprop=content&redirects&format=json' %(lang, message),
		'languagelist_json': 'http://%s.wikipedia.org/w/api.php?action=query&prop=langlinks&redirects&titles=%s&lllimit=500&format=json'  %(lang, message),
		'search_json': 'http://%s.wikipedia.org/w/api.php?action=query&list=search&srsearch=%s&sroffset=0&srlimit=5&format=json' % (lang, message),
		'article_html':'http://%s.wikipedia.org/w/index.php?action=view&title=%s' % (lang, message),
		'article_raw':'http://%s.wikipedia.org/w/index.php?action=raw&title=%s' % (lang, message)
	}
	return urlDict

# def getwikilang():
# 	# get the available languange list of wikipedia
# 	langListFile = open('langlist.txt')
# 	langlist = langListFile.read()
# 	langListFile.close()
# 	return langlist

def getwikilang():
	# get the available languange list of wikipedia
	url = 'http://en.wikipedia.org/w/api.php?action=query&meta=siteinfo&siprop=languages&format=json'
	content_raw = fetch(url)

	content = json.loads(content_raw)
	langs = content["query"]["languages"]
	langlist = ''

	for lang in langs:
		cc = lang["code"]
		ll = lang["*"]
		ll = ll.decode('unicode-escape')
		ll = re.sub(r'[\x80-\xFF]+', convert, ll)
		ll = ll.encode('utf8')
		langlist = '%s%s ------ %s \n' %(langlist, cc, ll)
	langlist = langlist + '%sen ------ English'

	return langlist

wikilang = getwikilang()
 

def detect_lang(query):
	# detect user input original language using detectlanguage.com API
	APIkey = '847dcd839991303e81cfa244de928a24'
	detectLangURL = 'http://ws.detectlanguage.com/0.2/detect?q=%s&key=%s' %(query, APIkey)
	detectLangUsageURL = 'http://ws.detectlanguage.com/0.2/user/status?key=%s' %APIkey
	detectLangUsageRaw = fetch(detectLangUsageURL)
	detectLangUsage = json.loads(detectLangUsageRaw)
	# check if the capacity is overflown
	if (detectLangUsage['requests']>detectLangUsage['daily_requests_limit']) or (detectLangUsage['bytes']>detectLangUsage['daily_bytes_limit']):
		return reply['detectLang-err']
	else:		
		detectRaw = fetch(detectLangURL)
		# convert the json-format string to dict
		result = json.loads(detectRaw)
		lang = result['data']['detections'][0][u'language']
		return lang

def trim4URL(message):
	# convert space from user input to plus to put in url safely
	message4URL = re.sub(' ','%20',message)
	return message4URL

def process_message(rawMessage):
	# strip unintended space at start or end
	message = rawMessage.strip()
	# if 'fk:' in message:
	# 		# this is considered a feedback message, the bot should reply with a thanks message.
	# 	return reply["feedback"]

	if '#' in message:
		# find user-specific language and trim message to only query
		langi = message.find('#') # the index where user specifies the target language
		messagelen = len(message)
		tarLangi = langi + 1
		tarLang = message[tarLangi - messagelen:].strip().lower() # store target language in a standalone string
		if tarLang in wikilang:
			message = message[0:langi] # trim the message to query only, hopefully
			message = message.strip()
			return (message,tarLang)
		else:
			return reply["language-code-err"]

	elif '#' not in message:
		tarLang = False
		return (message,tarLang)

def search(url):
		# get first 5 search result as a list
		search = json.loads(fetch(url))
		rl = search["query"]["search"]
		titlelist = []
		for r in rl:
			titlelist = titlelist + [r["title"]]
		return titlelist

def transfer_lang(message,tarLang):
	# deal with language transfermation requested by user
	# get the language list of this title
	message4URL = trim4URL(message)
	title4URL = message4URL
	lang = detect_lang(message4URL)
	avlLangURL = generate_url(message4URL,lang)['languagelist_json']
	avlLang = fetch(avlLangURL)
	# print avlLang
	if tarLang == False:
		title4URL = message4URL
		pass
	elif tarLang not in avlLang:
		replyMsg = reply['language-404']
		title4URL = message
		print replyMsg

	else:
		# if the bot needs to get result in a language other than input language
		
		# locate the targeted language, then get the according title in targeted language
		# the method used here is awfully hardcoded. Hopefully it can be improved later.
		pattern = '"lang":"%s"' % tarLang
		res = re.search(pattern, avlLang)

		if res == None:
			pass
		else:
			end = res.end()
			titlei = avlLang[end+6:].find('"}')
			title = avlLang[end+6:end+titlei+6]
			title = title.decode('unicode-escape')
			lang = tarLang
			title4URL = trim4URL(title.encode('utf-8'))

	return (title4URL,lang)

def get_article(title4URL, lang):
	articleJson = json.loads(fetch(generate_url(title4URL,lang)["article_json"]))
	if '-1' in articleJson['query']['pages']:
		searchURL = generate_url(title4URL,lang)["search_json"]
		# print searchURL
		searchList = search(searchURL)
		return searchList
	else:
		articleHTMLraw = fetch(generate_url(title4URL,lang)["article_html"])
		soup = BeautifulSoup.BeautifulSoup(articleHTMLraw)
		contentHTML = soup.find("div", {"id": "mw-content-text"}).find("p", recursive=False)
		pattern1 = '(<[^<>]+>)|(\[[0-9]+\])'
		pattern2 ='(\[[^\[\]]+\])'
		blank=''
		articlePlain1 = re.sub(pattern1,blank,str(contentHTML))
		articlePlain = re.sub(pattern2,blank,articlePlain1)
		return articlePlain


message_xml = '''
			  <xml>
			  <ToUserName><![CDATA[%s]]></ToUserName>
			  <FromUserName><![CDATA[%s]]></FromUserName>
			  <CreateTime>%s</CreateTime>
			  <MsgType><![CDATA[%s]]></MsgType>
			  <Content><![CDATA[%s]]></Content>
			  <FuncFlag>0</FuncFlag>
		  	  </xml>
		     '''

def output(getArticleResult, title4URL, lang, toUser, fromUser):
	# xml output for Wechat. http://mp.weixin.qq.com/cgi-bin/readtemplate?t=wxm-callbackapi-doc&lang=zh_CN

	list_xml_head = '''
					<xml>
					<ToUserName><![CDATA[%s]]></ToUserName>
					<FromUserName><![CDATA[%s]]></FromUserName>
					<CreateTime>%s</CreateTime>
					<MsgType><![CDATA[%s]]></MsgType>
					<Content><![CDATA[]]></Content>
					<ArticleCount>%d</ArticleCount>
					<Articles>
					'''
	list_xml_item = '''
					<item>
					<Title><![CDATA[%s]]></Title>
					<Description><![CDATA[%s]]></Description>
					<PicUrl><![CDATA[%s]]></PicUrl>
					<Url><![CDATA['http://%s.wikipedia.org/wiki/%s']]></Url>
					</item>
					'''
	list_xml_foot = '''
					</Articles>
					<FuncFlag>0</FuncFlag>
					</xml> 
					'''

	clock = int(time.time())
	MsgType_text = "text"
	MsgType_news = "news"
	imgURL = " "
	if str(type(getArticleResult)) == "<type 'list'>" :
		# this is a search 
		ArticleCount = len(getArticleResult)
		# print getArticleResult
		if ArticleCount == 0:
			reply_list = message_xml %(toUser,fromUser,clock,MsgType_text,'Oops, no result found.')
		else:
			list_xml_item_construct = ''
			list_xml_item_construct = list_xml_item %(re.sub('%20',' ',getArticleResult[0]),'',imgURL,lang,re.sub(' ','%20',getArticleResult[0]))
			i = 1
			while i < ArticleCount:
				list_xml_item_construct = list_xml_item_construct + list_xml_item %(re.sub('%20','0',getArticleResult[i]),'','',lang,re.sub(' ','%20',getArticleResult[i]))
				i = i + 1
			# Content_text = "No such page. Try search." #"没有找到对应的页面。以下是相应的搜索结果："
			# reply_message = message_xml %(toUser,fromUser,clock,MsgType_text,Content_text)
			reply_list = list_xml_head %(toUser,fromUser,clock,MsgType_news,ArticleCount) + list_xml_item_construct + list_xml_foot
		return reply_list
	else:
		# this is an article
		reply_article = list_xml_head %(toUser,fromUser,clock,MsgType_news,1) + list_xml_item %(re.sub('%20',' ',title4URL),getArticleResult,imgURL,lang,title4URL) + list_xml_foot
		return reply_article

# Code learnt from https://github.com/pakoo/weixin_public/blob/master/app.py
class weixin():

	def POST(self):
		body = web.data()
		print '\n\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>'
		print 'body:',body
		print '>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>'
		soup = BeautifulSoup.BeautifulSoup(body)
		self.userid  = soup.find('fromusername').text
		self.createtime = soup.find('createtime').text
		self.msgtype = soup.find('msgtype').text
		self.myid = soup.find('tousername').text
		if self.msgtype == 'text':
		    self.wxText = soup.find('content').text
		    print 'text:',self.wxText  
		elif self.msgtype == 'location':
		    self.location_x = soup.find('location_x').text 
		    self.location_y = soup.find('location_y').text 
		    self.location_scale = soup.find('scale').text 
		    self.location_lable = soup.find('label').text 
		    print 'x:',self.location_x  
		    print 'y:',self.location_y
		elif self.msgtype == 'image':
		    self.picurl = soup.find('picurl').text 
		    print 'pic url:',self.picurl 

		if self.msgtype == "text":
			processed = process_message(self.wxText)
			# print processed
			transfered = transfer_lang(processed[0],processed[1])
			# print transfered
			article_search = get_article(transfered[0],transfered[1])
			reply = output(article_search,transfered[0],transfered[1],self.userid,self.myid)
		elif self.msgtype == "location":
		 	comingsoon = "Location-based feature is coming soon. :)"
		 	reply = self.message_xml %(self.userid,self.myid,clock,MsgType_text,comingsoon)
		elif self.msgtype == "image":
			notinterested = "Oops, I'm not interested in your photo."
			reply = self.message_xml %(self.userid,self.myid,clock,MsgType_text,notinterested)

		print reply
		return

		# def send_text(self,output):
		# 	#self.set_header("Content-Type","application/xml; charset=UTF-8")
		# 	line = output 
		# 	self.finish(line)
    	
urls = ("/.*","weixin")
app = web.application(urls,globals())

if __name__ == '__main__':
	app.run()