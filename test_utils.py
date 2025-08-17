from utils import parse_rss
from rss_resources import RSS_FEEDS

result = parse_rss("FTC_consumer_blog", "https://consumer.ftc.gov/blog/gd-rss.xml")
print(result)