from utils import parse_rss
from utils import normalize_entry
from utils import normalize_many
from rss_resources import RSS_FEEDS
import json 

parsed_rss = parse_rss("FTC_consumer_blog", "https://consumer.ftc.gov/blog/gd-rss.xml")

normalized_rss = normalize_many(parsed_rss)
print(json.dumps(normalized_rss, indent=2))
