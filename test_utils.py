from utils import parse_rss
from utils import normalize_entry
from rss_resources import RSS_FEEDS

parsed_rss = parse_rss("FTC_consumer_blog", "https://consumer.ftc.gov/blog/gd-rss.xml")
print(parsed_rss)

normalized_rss = [normalize_entry(item) for item in parsed_rss]
print(normalized_rss)
