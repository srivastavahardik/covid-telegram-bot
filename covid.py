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
            if word[0] == '@' or word == "Replying to" or word == "and" or ("and" in word and "others" in word) == True:
                reply_index += 1
            else:
                break
        return list(tweet_content[reply_index:])

    def prettify_content(self, content):
        # Any post processing which needs to be applied to text
        content = str(content).strip()
        content = content.replace("  ", " ")
        return content
    
    # Match text patterns to see if tweet is valid
    def is_tweet_valid(self, content):
        not_have = ["please share any", "kindly provide", "please help people", "levels dropped to", "only please"]
        content = str(content).lower()
        for sent in not_have:
            if sent in content:
                return False
        return True
            

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
        unwanted = ["/profile_images/", "/emoji/", "profile_image", "hashflags"]
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
            tweet_time = datetime.strptime(twitter_time + ", 2021", "%d %b, %Y")
        return str(tweet_time.strftime("%Y-%m-%d %H:%M:%S"))

class Main:
    def __init__(self, links, tags, config):
        self.LINKS = list(links)
        for link in links:
            self.LATEST_TWEET.append(None)
        self.TAGS = list(tags)
        self.CONFIG = str(config)

    # TODO : Replace with custom link
    # Reference link
    LINKS = []
    LATEST_TWEET = []
    CURRENT = -1
    TAGS = []
    CONFIG = ""
    API_URL = "https://covid-aid.techburner.in/api/tweets"
    driver = None
    timeline = None
    parser = TweetParser()
    tweets = None

    # Setup options for chrome driver
    def setup_webdriver(self):
        # Setting up Chrome options
        # option = webdriver.FirefoxOptions()
        option = webdriver.ChromeOptions()
        # For ChromeDriver version 79.0.3945.16 or over
        # Hide automation
        option.add_argument('--disable-blink-features=AutomationControlled')
        # Start headlessly
        option.headless = False
        # Open Browser
        self.driver = webdriver.Chrome(options=option)

    def rotate_link(self):
        self.CURRENT += 1
        if self.CURRENT == len(self.LINKS):
            self.CURRENT = 0

    def launch_webdriver(self):
        self.rotate_link()
        # Opening search results
        self.driver.get(self.LINKS[self.CURRENT])

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
        if self.TAGS[self.CURRENT] != "":
            text += "\n #" + self.TAGS[self.CURRENT]
        if (self.CONFIG != ""):
            telegram_send.send(conf=str(self.CONFIG).lower(), messages=[text])
        else:
            telegram_send.send(messages=[text])

    def upload_to_db(self, parsed_tweet):
        # requests.post("https://covid-aid.techburner.in/api/tweets?content=check&resource=remdesivir&location=mumbai&tweeted_time=2021-04-25 06:22:46&attachments=[\"media/soham.jpg\", \"media/kk.jpg\"]&contacts=[\"872827892\", \"2877872672\"]")
        data = {
            "content": parsed_tweet.content,
            "resource": self.TAGS[self.CURRENT],
            "location": self.CONFIG,
            "tweeted_time": parsed_tweet.time,
            # "attachments": str(parsed_tweet.attachments),
            # "contacts": str(parsed_tweet.phone_numbers)
        }
        s = Session()
        p = Request('POST', self.API_URL, params=data).prepare()

        manual_url = p.url
        # manual_url += "&attachments=[\"wwa.google.com\", \"www.test.com\"]"
        manual_url += "&attachments=" + str(parsed_tweet.attachments).replace("'", "\"")
        manual_url += "&contacts=" + str(parsed_tweet.phone_numbers).replace("'", "\"")

        print("Pushing to server...")
        print(manual_url)
        requests.post(manual_url)

    # Runs infinitely to constantly find new tweets
    def scrape(self):
        self.launch_webdriver()
        self.find_timeline()
        # Children of this element = Root elements of tweets
        self.tweets = self.timeline.find_elements_by_xpath("./child::*")

    def check_new(self):
        self.scrape()
        top_tweet_parsed = self.parser.parse_tweet(self.tweets[0])
        if self.LATEST_TWEET[self.CURRENT] != top_tweet_parsed.content and self.parser.is_tweet_valid(top_tweet_parsed.content) == True:
            # New Tweet
            print(top_tweet_parsed.content)
            print(top_tweet_parsed.time)
            print(top_tweet_parsed.attachments)
            print(top_tweet_parsed.phone_numbers)
            self.upload_to_db(top_tweet_parsed)
            self.push_to_telegram(top_tweet_parsed)
            self.LATEST_TWEET[self.CURRENT] = top_tweet_parsed.content
        print("------------------------")

    def start(self):
        self.setup_webdriver()
        print("debug")
        while True:
            self.check_new()
            time.sleep(10)


def generate_link_group(location):
    return [
        "https://twitter.com/search?q=verified+" + str(location) + "+%28bed+OR+beds%29+-%22not+verified%22+-%22unverified%22+-%22needed%22+-%22need%22+-%22needs%22+-%22required%22+-%22require%22+-%22requires%22+-%22requirement%22+-%22requirements%22&f=live",
        "https://twitter.com/search?q=verified+" + str(location) + "+%28icu%29+-%22not+verified%22+-%22unverified%22+-%22needed%22+-%22need%22+-%22needs%22+-%22required%22+-%22require%22+-%22requires%22+-%22requirement%22+-%22requirements%22&f=live",
        "https://twitter.com/search?q=verified+" + str(location) + "+%28oxygen+OR+ventilator+OR+ventilators%29+-%22not+verified%22+-%22unverified%22+-%22needed%22+-%22need%22+-%22needs%22+-%22required%22+-%22require%22+-%22requires%22+-%22requirement%22+-%22requirements%22&f=live",
        "https://twitter.com/search?q=verified+" + str(location) + "+%28fabiflu+OR+remdesivir+OR+favipiravir+OR+tocilizumab%29+-%22not+verified%22+-%22unverified%22+-%22needed%22+-%22need%22+-%22needs%22+-%22required%22+-%22require%22+-%22requires%22+-%22requirement%22+-%22requirements%22&f=live",
        "https://twitter.com/search?q=verified+" + str(location) + "+%28plasma%29+-%22not+verified%22+-%22unverified%22+-%22needed%22+-%22need%22+-%22needs%22+-%22required%22+-%22require%22+-%22requires%22+-%22requirement%22+-%22requirements%22&f=live"
    ]

# Beds
# ICU
# Oxygen/Ventilator
# Medicine
# Plasma
tags = [
    "Beds",
    "ICU",
    "Oxygen",
    "Medicine",
    "Plasma"
]

if len(sys.argv) < 2:
    print("Please provide location as argument!")
    exit(1)

location = str(sys.argv[1])
print("Location provded: " + location)

links = generate_link_group(location)
scraper = Main(links, tags, location)
scraper.setup_webdriver()
while True:
    time.sleep(5)
    try:
        scraper.check_new()
    except:
        telegram_send.send(conf="error", messages=["Script errored for " + location])