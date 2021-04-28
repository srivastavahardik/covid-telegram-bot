#!/bin/python3
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import time
from datetime import datetime, timedelta
import re
import telegram_send
import sys
import requests
from requests import Session, Request

class TweetData:
    def __init__(self, content, time, is_verified, upvotes, attachments, phone_numbers):
        self.content = str(content)
        self.time = str(time)
        self.is_verified = bool(is_verified)
        self.upvotes = int(upvotes)
        self.attachments = list(attachments)
        self.phone_numbers = list(phone_numbers)

class TweetParser:
    def parse_tweet(self, tweet):
        try:
            # 'Jaideep Pandey\n@PandeyJaideep\n·\n1h\n#Lucknow #UPDATE #HospitalBeds #CovidHelp \n#Beds with #oxygen are available at St. Joseph Hospital in Gomti Nagar. Call:7947145417 #Verified at 1 AM. \n@awwwnchal\n @jeevika_shiv\n @neeleshmisra\n @Interceptors\n @bhaisaabpayal\n @YahyaRahmani19\n @lakhnauaa\n4\n3\n2'
            tweet_text = tweet.find_elements_by_class_name("css-1dbjc4n")
            # print("text: ")
            # First we cut using '·'
            # Take the second part
            # Then we cut using '\n'
            # [1:] because 0th element is empty item
            text_cut = str((str(tweet_text[0].text).split("·"))[1]).split("\n")[1:]
            tweet_age = self.get_tweet_age(text_cut)
            text_cut = self.clean_tweet_content(text_cut[1:])
            tweet_content = self.prettify_content(self.get_tweet_text(text_cut))
            tweet_media = tweet.find_elements_by_class_name("css-9pa8cd")
            medias = self.get_tweet_media(tweet_media)
            return TweetData(tweet_content, self.twime_to_string(tweet_age), False, 0, medias, self.extract_phone(tweet_content))
        except Exception as e:
            print(e)
            # no media
            return None
    
    def clean_tweet_content(self, tweet_content):
        tweet_content = list(tweet_content)
        # Remove starting content like 'Replying to @kumarmanish9 @AnupamkPandey and @AdminLKO'
        reply_index = 0
        and_encountered = False
        for word in tweet_content:
            word = str(word).strip()
            if word[0] == '@' or word == "Replying to" or word == "and":
                reply_index += 1
            else:
                break
        return list(tweet_content[reply_index:])

    def prettify_content(self, content):
        # Any post processing which needs to be applied to text
        content = str(content).strip()
        content = content.replace("  ", " ")
        return content

    def get_tweet_text(self, tweet_content):
        tweet_content = list(tweet_content)
        # print(text_cut)
        # 0th element of text_cut is the age of tweet
        # Last 3 elements include number of comments, number of retweets and number of likes
        # ^ all might not exist
        last_counter = 0
        if str(tweet_content[-1]).lower() == "show this thread":
            last_counter += 1
        
        for i in range(1 + last_counter, 4 + last_counter):
            try:
                # Assuming that the tweet is <1m in age
                if int(tweet_content[-i]) < 50:
                    last_counter += 1
            except:
                pass

        tweet_text = tweet_content
        if last_counter != 0:
            tweet_text = tweet_content[0:-last_counter]
        tweet_content = " ".join(tweet_text)
        return str(tweet_content)

    def get_tweet_age(self, tweet_content):
        tweet_content = list(tweet_content)
        return str(tweet_content[0])

    def get_tweet_media(self, tweet_media):
        tweet_media = list(tweet_media)
        medias = []
        for media in tweet_media:
            media_src = media.get_attribute("src")
            if self.is_media_valid(media_src) == True:
                medias.append(media_src)
        return medias

    def is_media_valid(self, url):
        unwanted = ["/profile_images/", "/emoji/", "profile_image"]
        for unw in unwanted:
            if unw in url:
                return False
        return True

    # https://dev.to/samcodesign/phone-number-email-extractor-with-python-12g2
    def extract_phone(self, content):
        phoneRegex = re.compile(r'''(
            (\d{2}|\(\d{2}\))? # area code
            (\s|-|\.)? # separator
            (\d{5}) # first 5 digits
            (\s|-|\.|) # separator
            (\d{5}) # last 5 digits
        )''', re.VERBOSE)
        matches = []
        for groups in phoneRegex.findall(content):
            phoneNum = ''.join([groups[1], groups[3], groups[5]])
            matches.append(str(phoneNum))
        return matches
    
    # twime = twitter time
    def twime_to_string(self, twitter_time):
        # 45s 5m 3h Apr 24
        # converted to : 202104250422
        twitter_time = str(twitter_time)
        tweet_time = None
        if len(twitter_time) <= 3:
            last_char = twitter_time[-1]
            diff = None
            if last_char == 's':
                diff = timedelta(seconds=int(twitter_time[0:-1]))
            elif last_char == 'm':
                diff = timedelta(minutes=int(twitter_time[0:-1]))
            elif last_char == 'h':
                diff = timedelta(hours=int(twitter_time[0:-1]))
            now = datetime.now()
            tweet_time = now - diff
        else:
            if "2021" in str(twitter_time) == False:
                tweet_time += ", 2021" 
            tweet_time = datetime.strptime(twitter_time, "%b %d, %Y")
        return str(tweet_time.strftime("%Y-%m-%d %H:%M:%S"))

class Main:
    def __init__(self, link, tag, config):
        self.LINK = str(link)
        self.TAG = str(tag)
        self.CONFIG = str(config)

    # TODO : Replace with custom link
    # Reference link
    LINK = "https://twitter.com/search?q=verified+Mumbai+%28remdesivir%29+-%22not+verified%22+-%22unverified%22+-%22needed%22+-%22need%22+-%22needs%22+-%22required%22+-%22require%22+-%22requires%22+-%22requirement%22+-%22requirements%22&f=live"
    # LINK = "https://twitter.com/search?q=verified+lucknow+%28bed+OR+beds+OR+icu+OR+oxygen+OR+ventilator+OR+ventilators%29+-%22not+verified%22+-%22unverified%22+-%22needed%22+-%22need%22+-%22needs%22+-%22required%22+-%22require%22+-%22requires%22+-%22requirement%22+-%22requirements%22&f=live"
    TAG = ""
    CONFIG = ""
    API_URL = "https://covid-aid.techburner.in/api/tweets"
    driver = None
    timeline = None

    # Setup options for chrome driver
    def setup_webdriver(self):
        # Setting up Chrome options
        # option = webdriver.FirefoxOptions()
        option = webdriver.ChromeOptions()
        # For ChromeDriver version 79.0.3945.16 or over
        # Hide automation
        option.add_argument('--disable-blink-features=AutomationControlled')
        # Start headlessly
        option.headless = True
        # Open Browser
        self.driver = webdriver.Chrome(options=option)

    def launch_webdriver(self):
        # Opening search results
        self.driver.get(self.LINK)

    def move_page(self):
        self.driver.execute_script("window.scrollTo(0, window.scrollY + 250)")
        for i in range(0, 10):
            self.driver.execute_script("window.scrollTo(0, window.scrollY - 100)")

    def find_timeline(self):
        # Trap loop to keep waiting for timeline to load
        timeline_parent = None
        while (timeline_parent == None):
            try:
                timeline_parent = self.driver.find_element_by_xpath("//div[@aria-label='Timeline: Search timeline']")
            except:
                pass
        # Trap loop to wait for content to load
        while (len(str(timeline_parent.text)) == 0):
            self.move_page()
            time.sleep(1)
        #####
        # At this point we are mostly sure that the timeline has loaded
        #####
        # First and only Child of timeline_parent is the actual timeline list element
        self.timeline = (timeline_parent.find_elements_by_xpath("./child::*"))[0]
    
    def push_to_telegram(self, parsed_tweet):
        attachment_text = ""
        for attach in parsed_tweet.attachments:
            attachment_text += str(attach) + "\n"
        phone_text = ""
        for phn in parsed_tweet.phone_numbers:
            phone_text += str(phn) + "\n"

        text = parsed_tweet.content + "\n\n" + parsed_tweet.time
        if attachment_text != "":
            text += "\nAttachments: \n" + attachment_text
        if phone_text != "":
            text += "\nPhone Numbers: \n" + phone_text
        # text = parsed_tweet.content + "\n\n" + parsed_tweet.time + "\n" + "Attachements: \n" + attachment_text + "Phone Numbers: \n" + phone_text
        # text = text.replace("\n", "%0A")
        # text = text.replace(" ", "%20")
        # print(text)
        if self.TAG != "":
            text += "\n " + self.TAG
        if (self.CONFIG != ""):
            telegram_send.send(conf=self.CONFIG, messages=[text])
        else:
            telegram_send.send(messages=[text])

    def upload_to_db(self, parsed_tweet):
        # https://covid-aid.techburner.in/api/tweets?content=check&resource=remdesivir&location=mumbai&tweeted_time=2021-04-25 06:22:46&attachments=["media/soham.jpg", "media/kk.jpg"]&contacts=["872827892", "2877872672"]
        data = {
            "content": parsed_tweet.content,
            "resource": self.TAG,
            "location": self.CONFIG,
            "tweeted_time": parsed_tweet.time,
            # "attachments": str(parsed_tweet.attachments),
            # "contacts": str(parsed_tweet.phone_numbers)
        }
        s = Session()
        p = Request('POST', self.API_URL, params=data).prepare()

        manual_url = p.url
        manual_url += "&attachments=" + str(parsed_tweet.attachments).replace("'", "\"")
        # contact_part = ' '.join([("\"" + str(num) + "\",") for num in parsed_tweet.phone_numbers])
        manual_url += "&contacts=" + str(parsed_tweet.phone_numbers).replace("'", "\"")

        print("Pushing to server...")
        print(manual_url)
        requests.post(manual_url)
        # requests.post("https://covid-aid.techburner.in/api/tweets?content=check&resource=remdesivir&location=mumbai&tweeted_time=2021-04-25 06:22:46&attachments=[\"media/soham.jpg\", \"media/kk.jpg\"]&contacts=[\"872827892\", \"2877872672\"]")
        # s.send(manual_url)

    # Runs infinitely to constantly find new tweets
    def scrape(self):
        parser = TweetParser()
        latest_tweet = None

        self.move_page()
        # Children of this element = Root elements of tweets
        tweets = self.timeline.find_elements_by_xpath("./child::*")
        print(len(tweets))
        for tweet in reversed(tweets):
            parsed = parser.parse_tweet(tweet)
            if parsed != None:
                print(parsed.content)
                print(parsed.time)
                print(parsed.attachments)
                print(parsed.phone_numbers)
                self.upload_to_db(parsed)
                # self.push_to_telegram(parsed)
            print("------------------------")
        latest_tweet = parser.parse_tweet(tweets[0]).content
        while True:
            time.sleep(60)
            # Refreshing because often the page would go stale
            self.launch_webdriver()
            self.find_timeline()
            tweets = self.timeline.find_elements_by_xpath("./child::*")
            if latest_tweet != parser.parse_tweet(tweets[0]).content:
                latest_tweet = tweets[0]
                parsed_latest = parser.parse_tweet(latest_tweet)
                # Normalising the point of comparison
                latest_tweet = parsed_latest.content
                print(parsed_latest.content)
                print(parsed_latest.time)
                print(parsed_latest.attachments)
                print(parsed_latest.phone_numbers)
                # self.push_to_telegram(parsed_latest)
            print("------------------------")

    def start(self):
        self.setup_webdriver()
        self.launch_webdriver()
        self.find_timeline()
        print("debug")
        self.scrape()

# link, tag, telegram_send config
main = None
if len(sys.argv) == 1:
    print("Please enter link!")
    exit()
elif len(sys.argv) == 2:
    main = Main(sys.argv[1], "", "")
elif len(sys.argv) == 3:
    main = Main(sys.argv[1], sys.argv[2], "")
elif len(sys.argv) == 4:
    main = Main(sys.argv[1], sys.argv[2], sys.argv[3])


while True:
    main.start()