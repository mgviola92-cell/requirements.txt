# Telegram news reader

`/news` retains the existing headline list and adds one numbered Read button per visible story. Read edits the same tracked message, with Previous/Next, Back to list and the publisher's original link. Every callback renews the existing five-minute inactivity deadline; expired/untracked cards cannot be revived.

The reader displays the owner's brief first, otherwise an attributed feed extract (at most 100 whitespace-separated words and 1,200 characters). RSS description/summary and content:encoded/Atom content are supported. HTML/scripts are removed and display text is escaped. No AI, automatic translation, full article scraping or headline-based invented summary is used. A missing extract is explicitly reported.

Feed extracts share the existing news_items JSON cache across groups. No new tables or per-click publisher requests. Conditional feed validators are refreshed once for this reader version to populate old headline-only records; later fetches retain ETag/Last-Modified support. Existing owner briefs survive feed refreshes. Story callbacks contain stable item IDs and resolve only against the current selected sources and age window; removed stories show a refresh notice. Neighbor order follows the current cache, so new stories may shift the list.

Manual and automatic digest cards both receive Read buttons. Source failures preserve the last cache. Telegram cards remain shared within a group: another member's tap changes the same card.

Validation: targeted parser, reader/navigation, markup, callback/deadline and existing bandwidth tests. Live probes returned 10 readable items each for Myanmar Now and SHAN; Irrawaddy failed with URLError in the development environment. Feed availability and publisher-provided detail vary. New extracts appear after the next scheduled successful feed refresh.
