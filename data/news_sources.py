"""Curated RSS adapters. Failed or stale feeds are reported, never counted as working.
Language editions of one publisher share the same family for source counting.
"""
SOURCES=[
 ('myanmar_now','Myanmar Now','https://myanmar-now.org/mm/feed/','myanmarnow',True),
 ('irrawaddy','ဧရာဝတီ','https://burma.irrawaddy.com/feed/','irrawaddy',True),
 ('dvb','DVB','https://burmese.dvb.no/feed/','dvb',True),
 ('mizzima','Mizzima','https://bur.mizzima.com/feed/','mizzima',True),
 ('bbc_burmese','BBC မြန်မာ','https://feeds.bbci.co.uk/burmese/rss.xml','bbc',True),
 ('rfa','RFA မြန်မာ','https://www.rfa.org/burmese/rss2.xml','rfa',True),
 ('voa','VOA မြန်မာ','https://burmese.voanews.com/api/zb_u_l-vomx-tpeqrjy','voa',True),
 ('frontier','Frontier Myanmar','https://www.frontiermyanmar.net/en/feed/','frontier',True),
 ('frontier_mm','Frontier မြန်မာ','https://www.frontiermyanmar.net/mm/feed/','frontier',True),
 ('kachin','Kachin News Group','https://burmese.kachinnews.com/feed/','kachin',True),
 ('kic','Karen Information Center','https://kicnews.org/feed/','kic',True),
 ('karen','Karen News','https://karennews.org/feed/','kic',True),
 ('shan','SHAN','https://burmese.shannews.org/feed','shan',True),
 ('mon','Independent Mon News Agency','https://burmese.monnews.org/feed/','mon',True),
 ('thanlwin','Than Lwin Times','https://thanlwintimes.com/feed/','thanlwin',True),
 ('dawei','Dawei Watch','https://www.daweiwatch.com/feed/','dawei',True),
 ('khitthit','Khit Thit Media','https://yktnews.com/feed/','khitthit',True),
 ('bbc_asia','BBC Asia','https://feeds.bbci.co.uk/news/world/asia/rss.xml','bbc',False),
 ('guardian','The Guardian / Myanmar','https://www.theguardian.com/world/myanmar/rss','guardian',False),
 ('aljazeera','Al Jazeera','https://www.aljazeera.com/xml/rss/all.xml','aljazeera',False),
 ('france24','France 24','https://www.france24.com/en/asia-pacific/rss','france24',False),
 ('cna','Channel NewsAsia','https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=6511','cna',False),
 ('dw','Deutsche Welle','https://rss.dw.com/rdf/rss-en-all','dw',False),
 ('reuters','Reuters / indexed RSS','https://news.google.com/rss/search?q=site:reuters.com+Myanmar+when:3d&hl=en-US&gl=US&ceid=US:en','reuters',False),
 ('ap','Associated Press / indexed RSS','https://news.google.com/rss/search?q=site:apnews.com+Myanmar+when:3d&hl=en-US&gl=US&ceid=US:en','ap',False),
]
CATALOG={row[0]:dict(zip(('id','name','url','family','local'),row)) for row in SOURCES}
