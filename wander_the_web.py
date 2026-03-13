"""
wander_the_web.py
-----------------
Builds elite third-party cookie profiles by wandering the web.
[UPGRADED]: Introduces 'Mode C: External Referrer Strike' to generate 
massive off-platform algorithmic authority for YouTube videos.
"""

import os
import asyncio
import logging
import random
import urllib.parse
from pathlib import Path
from playwright.async_api import Page

# Import the elite physics and timing primitives
from behavior_engine import (
    human_scroll, 
    click_humanly, 
    idle_reading, 
    smart_wait, 
    lognormal_delay
)
from llm_helper import generate_dynamic_search

log = logging.getLogger(__name__)

# ==========================================
# 🔗 EXTERNAL REFERRER LINKS (YOUTUBE STRIKE)
# ==========================================
# Put your Reddit threads, Twitter posts, Medium articles, or custom blogs here.
# Alternatively, create a file named "referrers.txt" in this directory and paste links there (one per line).
EXTERNAL_REFERRER_LINKS = [
    # "https://www.reddit.com/r/YourSubreddit/comments/xyz/your_post/",
    # "https://twitter.com/YourHandle/status/123456789",
    # "https://your-custom-blog.com/article-about-video/"
]

def load_referrers():
    """Loads external referrers from referrers.txt if it exists, scaling to infinite links."""
    referrers = list(EXTERNAL_REFERRER_LINKS) # Copy base list
    try:
        ref_file = Path(__file__).parent / "referrers.txt"
        if ref_file.exists():
            with open(ref_file, "r") as f:
                file_links = [line.strip() for line in f if line.strip() and not line.startswith("#")]
                referrers.extend(file_links)
    except Exception as e:
        log.warning(f"Could not load referrers.txt: {e}")
    return referrers

# ==========================================
# 🌐 MASSIVE SEARCH DIRECTORIES LIST
# ==========================================
SEARCH_DIRECTORIES = [
    # ---- Major Search Engines ----
    "https://duckduckgo.com/?q=",
    "https://www.bing.com/search?q=",
    "https://search.yahoo.com/search?p=",
    "https://www.ecosia.org/search?q=",
    "https://search.brave.com/search?q=",
    "https://www.startpage.com/search?q=",
    # (Assume the rest of your 200+ search URLs are here - keep them in your actual code)
]

# ==========================================
# 🌐 MASSIVE SEARCH DIRECTORIES LIST
# ==========================================
SEARCH_DIRECTORIES = [

    # ---- Major Search Engines ----
    "https://duckduckgo.com/?q=",
    "https://www.bing.com/search?q=",
    "https://search.yahoo.com/search?p=",
    "https://www.ecosia.org/search?q=",
    "https://www.ask.com/web?q=",
    "https://www.dogpile.com/serp?q=",
    "https://search.brave.com/search?q=",
    "https://www.startpage.com/search?q=",
    "https://www.mojeek.com/search?q=",
    "https://www.gibiru.com/results.html?q=",
    "https://www.search.com/search?q=",
    "https://www.wolframalpha.com/input?i=",
    "https://www.gigablast.com/search?q=",
    "https://www.yandex.com/search/?text=",
    "https://www.baidu.com/s?wd=",
    "https://www.swisscows.com/en/web?query=",
    "https://www.metacrawler.com/serp?q=",
    "https://search.lycos.com/web/?q=",
    "https://www.entireweb.com/web/?q=",
    "https://www.info.com/serp?q=",

    # ---- E-Commerce & Retail ----
    "https://www.amazon.com/s?k=",
    "https://www.ebay.com/sch/i.html?_nkw=",
    "https://www.target.com/s?searchTerm=",
    "https://www.walmart.com/search?q=",
    "https://www.etsy.com/search?q=",
    "https://www.aliexpress.com/wholesale?SearchText=",
    "https://www.wayfair.com/keyword.php?keyword=",
    "https://www.bestbuy.com/site/searchpage.jsp?st=",
    "https://www.homedepot.com/s/",
    "https://www.lowes.com/search?searchTerm=",
    "https://www.overstock.com/search?keywords=",
    "https://www.newegg.com/p/pl?d=",
    "https://www.costco.com/CatalogSearch?keyword=",
    "https://www.zappos.com/search?term=",
    "https://www.nordstrom.com/sr?origin=keywordsearch&keyword=",
    "https://www.macys.com/shop/featured/",
    "https://www.sephora.com/search?keyword=",
    "https://www.bhphotovideo.com/c/search?Ntt=",
    "https://www.adorama.com/l/?searchinfo=",
    "https://www.chewy.com/s?query=",
    "https://www.petco.com/shop/en/petcostore/search?query=",
    "https://www.ikea.com/us/en/search/?q=",
    "https://www.gap.com/browse/search.do?searchText=",
    "https://www.zara.com/us/en/search?searchTerm=",
    "https://www.hm.com/us/product/search.do?q=",
    "https://www.uniqlo.com/us/en/search?q=",
    "https://www.rei.com/search?q=",
    "https://www.cabelas.com/shop/en/search?q=",
    "https://www.autozone.com/searchresult?searchtext=",
    "https://www.rockauto.com/en/catalog/?q=",
    "https://shop.lego.com/en-US/search?q=",
    "https://www.staples.com/search#query=",
    "https://www.officedepot.com/catalog/search.do?Ntt=",
    "https://www.petsmart.com/search?q=",
    "https://www.wish.com/search/",
    "https://www.shein.com/pdsearch/",
    "https://www.temu.com/search_result.html?search_key=",
    "https://www.instacart.com/products/search?q=",

    # ---- Social & Community ----
    "https://www.reddit.com/search/?q=",
    "https://www.quora.com/search?q=",
    "https://www.youtube.com/results?search_query=",
    "https://medium.com/search?q=",
    "https://www.tumblr.com/search/",
    "https://www.pinterest.com/search/pins/?q=",
    "https://www.deviantart.com/search?q=",
    "https://www.flickr.com/search/?text=",
    "https://www.behance.net/search/projects?search=",
    "https://www.dribbble.com/search?q=",
    "https://stackoverflow.com/search?q=",
    "https://www.discord.com/search?q=",
    "https://news.ycombinator.com/search?q=",
    "https://lobste.rs/search?q=",
    "https://www.producthunt.com/search?q=",
    "https://hashnode.com/search?q=",
    "https://dev.to/search?q=",
    "https://community.hubspot.com/t5/forums/searchpage/tab/message?q=",
    "https://www.goodreads.com/search?q=",
    "https://www.letterboxd.com/search/",
    "https://www.last.fm/search?q=",
    "https://genius.com/search?q=",
    "https://www.songkick.com/search?query=",
    "https://bandcamp.com/search?q=",
    "https://soundcloud.com/search?q=",
    "https://mixcloud.com/search/?q=",

    # ---- Reference & Education ----
    "https://en.wikipedia.org/w/index.php?search=",
    "https://www.britannica.com/search?query=",
    "https://www.dictionary.com/browse/",
    "https://www.thesaurus.com/browse/",
    "https://www.merriam-webster.com/dictionary/",
    "https://www.vocabulary.com/dictionary/",
    "https://www.etymonline.com/search?q=",
    "https://scholar.google.com/scholar?q=",
    "https://pubmed.ncbi.nlm.nih.gov/?term=",
    "https://arxiv.org/search/?searchtype=all&query=",
    "https://www.jstor.org/action/doBasicSearch?Query=",
    "https://www.coursera.org/search?query=",
    "https://www.udemy.com/courses/search/?q=",
    "https://www.edx.org/search?q=",
    "https://www.khanacademy.org/search?page_search_query=",
    "https://www.skillshare.com/en/search?query=",
    "https://www.masterclass.com/search?q=",
    "https://www.lynda.com/search?q=",
    "https://www.ted.com/search?q=",
    "https://ocw.mit.edu/search/?q=",
    "https://www.gutenberg.org/ebooks/search/?query=",
    "https://openlibrary.org/search?q=",
    "https://archive.org/search?query=",
    "https://librivox.org/search?primary_key=&search_form=advanced&q=",
    "https://www.sparknotes.com/search/?q=",
    "https://www.cliffsnotes.com/search?q=",
    "https://www.wolframalpha.com/input?i=",
    "https://www.researchgate.net/search?q=",
    "https://www.academia.edu/search?q=",
    "https://eric.ed.gov/?q=",
    "https://doaj.org/search/articles?ref=homepage&query=",
    "https://www.sciencedirect.com/search?qs=",
    "https://link.springer.com/search?query=",
    "https://www.semanticscholar.org/search?q=",

    # ---- Health & Wellness ----
    "https://www.webmd.com/search/search_results/default?query=",
    "https://www.healthline.com/search?q1=",
    "https://www.mayoclinic.org/search/search-results?q=",
    "https://medlineplus.gov/search.html?query=",
    "https://www.drugs.com/search.php?searchterm=",
    "https://www.rxlist.com/search/rxl/",
    "https://www.everydayhealth.com/search/?query=",
    "https://www.medicalnewstoday.com/search?q=",
    "https://www.nih.gov/search/search-results?q=",
    "https://www.cdc.gov/search/index.html?query=",
    "https://www.who.int/home/search?indexCatalogue=genericsearchindex1&searchQuery=",
    "https://www.menshealth.com/search/?q=",
    "https://www.womenshealthmag.com/search/?q=",
    "https://www.shape.com/search?q=",
    "https://www.runnersworld.com/search/?q=",
    "https://www.bodybuilding.com/content/search.html?q=",
    "https://examine.com/search/?q=",
    "https://www.nutritionvalue.org/",
    "https://nutritiondata.self.com/foods-",
    "https://www.calorieking.com/us/en/foods/search?keywords=",
    "https://www.myfitnesspal.com/food/search?search=",

    # ---- Food & Recipes ----
    "https://www.allrecipes.com/search?q=",
    "https://www.foodnetwork.com/search/",
    "https://www.epicurious.com/search/",
    "https://www.seriouseats.com/search?q=",
    "https://www.bonappetit.com/search?q=",
    "https://tasty.co/search?q=",
    "https://www.bbcgoodfood.com/search?q=",
    "https://www.delish.com/search/?q=",
    "https://www.simplyrecipes.com/search?q=",
    "https://www.yummly.com/recipes?q=",
    "https://www.food.com/search/",
    "https://www.cookinglight.com/search/?q=",
    "https://www.eating well.com/search?q=",
    "https://www.101cookbooks.com/search/",
    "https://minimalistbaker.com/?s=",
    "https://www.halfbakedharvest.com/?s=",
    "https://www.skinnytaste.com/?s=",
    "https://www.budgetbytes.com/?s=",
    "https://www.themediterraneandish.com/?s=",
    "https://www.yelp.com/search?find_desc=",

    # ---- Travel & Geography ----
    "https://www.tripadvisor.com/Search?q=",
    "https://www.expedia.com/Hotel-Search?destination=",
    "https://www.booking.com/search.html?ss=",
    "https://www.airbnb.com/s/",
    "https://www.kayak.com/hotels/",
    "https://www.hotels.com/search.do?q-destination=",
    "https://www.travelocity.com/search/results?",
    "https://www.lonelyplanet.com/search?q=",
    "https://www.roughguides.com/search/?q=",
    "https://www.fodors.com/search?q=",
    "https://www.nationalgeographic.com/search?q=",
    "https://www.atlasobscura.com/search?q=",
    "https://www.travelandleisure.com/search?q=",
    "https://www.cntraveler.com/search?q=",
    "https://www.frommers.com/search?q=",
    "https://wikitravel.org/en/Special:Search?search=",
    "https://www.rome2rio.com/s/",
    "https://www.seat61.com/search.htm?q=",

    # ---- Finance & Business ----
    "https://finance.yahoo.com/quote/",
    "https://www.bloomberg.com/search?query=",
    "https://www.investopedia.com/search#q=",
    "https://www.cnbc.com/search/?query=",
    "https://www.marketwatch.com/search?q=",
    "https://seekingalpha.com/search?q=",
    "https://www.thestreet.com/search?q=",
    "https://www.fool.com/search/solr.aspx?q=",
    "https://finviz.com/screener.ashx?v=111&f=",
    "https://stockanalysis.com/stocks/",
    "https://simplywall.st/search?q=",
    "https://www.wisesheets.io/search?q=",
    "https://coinmarketcap.com/search/?q=",
    "https://www.coingecko.com/en/search?query=",
    "https://cryptocompare.com/#/search/",
    "https://www.crunchbase.com/search/organizations/field/organizations/facet_ids/company?q=",
    "https://pitchbook.com/search#q=",
    "https://www.glassdoor.com/Search/results.htm?keyword=",
    "https://www.linkedin.com/jobs/search/?keywords=",
    "https://www.indeed.com/jobs?q=",
    "https://www.ziprecruiter.com/jobs-search?search%5Bterms%5D=",
    "https://www.monster.com/jobs/search?q=",
    "https://www.simplyhired.com/search?q=",

    # ---- Technology & Programming ----
    "https://stackoverflow.com/search?q=",
    "https://github.com/search?q=",
    "https://gitlab.com/search?search=",
    "https://pypi.org/search/?q=",
    "https://www.npmjs.com/search?q=",
    "https://packagist.org/?query=",
    "https://crates.io/search?q=",
    "https://rubygems.org/search?query=",
    "https://hub.docker.com/search?q=",
    "https://marketplace.visualstudio.com/search?term=",
    "https://extensions.gnome.org/search/?q=",
    "https://alternativeto.net/browse/search/?q=",
    "https://www.slant.co/search#query=",
    "https://www.g2.com/search?query=",
    "https://www.capterra.com/search/?query=",
    "https://www.producthunt.com/search?q=",
    "https://devdocs.io/#q=",
    "https://css-tricks.com/?s=",
    "https://smashingmagazine.com/?s=",
    "https://www.sitepoint.com/search/",
    "https://www.w3schools.com/tags/",
    "https://developer.mozilla.org/en-US/search?q=",
    "https://docs.python.org/3/search.html?q=",
    "https://www.geeksforgeeks.org/search/?query=",
    "https://www.hackerrank.com/search?query=",
    "https://leetcode.com/problems/search/?q=",
    "https://codepen.io/search/pens?q=",
    "https://jsfiddle.net/search/?q=",

    # ---- News & Journalism ----
    "https://www.reuters.com/search/news?blob=",
    "https://apnews.com/search?q=",
    "https://www.theguardian.com/search?q=",
    "https://www.nytimes.com/search?query=",
    "https://www.washingtonpost.com/search/?query=",
    "https://www.wsj.com/search?query=",
    "https://www.usatoday.com/search/results/?q=",
    "https://www.latimes.com/search?q=",
    "https://www.chicagotribune.com/search/",
    "https://nypost.com/search/",
    "https://www.huffpost.com/search?q=",
    "https://www.politico.com/search?q=",
    "https://thehill.com/?s=",
    "https://www.axios.com/search?q=",
    "https://www.vox.com/search?q=",
    "https://www.vice.com/en/search/",
    "https://www.buzzfeednews.com/search?q=",
    "https://www.propublica.org/search/#q=",
    "https://www.aljazeera.com/search?q=",
    "https://www.dw.com/search/?languageCode=en&item=",
    "https://www.france24.com/en/search/?q=",
    "https://www.rt.com/search/?q=",
    "https://timesofindia.indiatimes.com/topic/",
    "https://www.smh.com.au/search-results?q=",
    "https://www.abc.net.au/search?q=",
    "https://ground.news/search?q=",
    "https://news.google.com/search?q=",
    "https://flipboard.com/search/",

    # ---- Entertainment & Media ----
    "https://www.imdb.com/find/?q=",
    "https://www.rottentomatoes.com/search/?search=",
    "https://letterboxd.com/search/",
    "https://trakt.tv/search?query=",
    "https://www.tvmaze.com/search?q=",
    "https://thetvdb.com/search?query=",
    "https://www.justwatch.com/us/search?q=",
    "https://www.metacritic.com/search/",
    "https://www.gamespot.com/search/?q=",
    "https://www.ign.com/search?q=",
    "https://www.polygon.com/search?q=",
    "https://www.kotaku.com/search?q=",
    "https://store.steampowered.com/search/?term=",
    "https://www.gog.com/en/games?genres=&devpub=&system=&price=&sort=bestselling&search=",
    "https://www.rawg.io/search?q=",
    "https://howlongtobeat.com/games?q=",
    "https://www.backloggd.com/games/lib/search/results/",
    "https://www.allmusic.com/search/all/",
    "https://www.discogs.com/search/?q=",
    "https://open.spotify.com/search/",
    "https://music.apple.com/search?term=",
    "https://tidal.com/search?q=",
    "https://www.songkick.com/search?query=",

    # ---- Books & Literature ----
    "https://www.goodreads.com/search?q=",
    "https://openlibrary.org/search?q=",
    "https://www.worldcat.org/search?q=",
    "https://www.librarything.com/search.php?search=",
    "https://www.bookfinder.com/search/?author=&title=&isbn=&new_used=*&binding=*&currency=USD&destination=us&mode=basic&lang=en&st=sr&ac=qr&keywords=",
    "https://www.abebooks.com/servlet/SearchResults?kn=",
    "https://www.alibris.com/search/books/keyword/",
    "https://www.powells.com/searchresults?keyword=",
    "https://www.barnesandnoble.com/s/",
    "https://www.thriftbooks.com/browse/?b.search=",
    "https://www.scribd.com/search?query=",
    "https://www.overdrive.com/search?q=",
    "https://www.audible.com/search?keywords=",
    "https://standardebooks.org/ebooks?query=",
    "https://manybooks.net/search/?search_keys=",
    "https://www.smashwords.com/books/search?query=",
    "https://www.draft2digital.com/store/search/",
    "https://www.wattpad.com/search/",
    "https://www.royal-road.com/fictions/search?title=",
    "https://www.fanfiction.net/search.php?ready=1&type=story&keywords=",
    "https://archiveofourown.org/works/search?work_search[query]=",

    # ---- Science & Nature ----
    "https://www.sciencedaily.com/search/?keyword=",
    "https://www.newscientist.com/search/?q=",
    "https://www.scientificamerican.com/search/?q=",
    "https://www.nature.com/search?q=",
    "https://www.science.org/action/doSearch?AllField=",
    "https://www.pnas.org/action/doSearch?AllField=",
    "https://www.cell.com/action/doSearch?query=",
    "https://www.nasa.gov/search-results/?q=",
    "https://spaceweather.com/?q=",
    "https://www.space.com/search?searchTerm=",
    "https://earthsky.org/?s=",
    "https://www.nationalgeographic.com/search?q=",
    "https://www.audubon.org/search?search_api_views_fulltext=",
    "https://www.inaturalist.org/search?q=",
    "https://ebird.org/explore",
    "https://www.allaboutbirds.org/guide/search/",
    "https://www.iucnredlist.org/search?query=",
    "https://www.gbif.org/species/search?q=",
    "https://animaldiversity.org/search.php?q=",

    # ---- Sports & Fitness ----
    "https://www.espn.com/search/_/q/",
    "https://www.cbssports.com/search/",
    "https://sports.yahoo.com/search?p=",
    "https://www.bleacherreport.com/search?q=",
    "https://www.sportingnews.com/us/search?q=",
    "https://www.basketball-reference.com/search/search.fcgi?search=",
    "https://www.baseball-reference.com/search/search.fcgi?search=",
    "https://www.pro-football-reference.com/search/search.fcgi?search=",
    "https://www.hockey-reference.com/search/search.fcgi?search=",
    "https://fbref.com/en/search/search.fcgi?search=",
    "https://www.transfermarkt.us/schnellsuche/ergebnis/schnellsuche?query=",
    "https://www.sofascore.com/search",
    "https://www.whoscored.com/Search/",
    "https://www.flashscore.com/search/?q=",
    "https://www.livescore.com/en/search/?q=",
    "https://www.strava.com/athletes/search?text=",
    "https://www.garmin.com/en-US/search/#q=",
    "https://www.trailforks.com/search/?q=",
    "https://www.alltrails.com/explore?q=",
    "https://www.hikingproject.com/route/find?q=",

    # ---- Art, Design & Photography ----
    "https://www.deviantart.com/search?q=",
    "https://www.behance.net/search/projects?search=",
    "https://dribbble.com/search?q=",
    "https://www.artstation.com/search?sort_by=likes&query=",
    "https://www.flickr.com/search/?text=",
    "https://unsplash.com/s/photos/",
    "https://www.pexels.com/search/",
    "https://pixabay.com/images/search/",
    "https://www.shutterstock.com/search/",
    "https://stock.adobe.com/search?k=",
    "https://www.gettyimages.com/search/2/image?phrase=",
    "https://www.istockphoto.com/search/2/image?phrase=",
    "https://500px.com/search?q=",
    "https://www.smugmug.com/gallery/search/?q=",
    "https://www.pinterest.com/search/pins/?q=",
    "https://www.creativebloq.com/search?q=",
    "https://www.designspiration.com/search/saves/?q=",
    "https://fonts.google.com/?query=",
    "https://www.dafont.com/search.php?q=",
    "https://www.fontsquirrel.com/fonts/list/find_fonts?q%5Bterm%5D=",
    "https://thenounproject.com/search/?q=",
    "https://www.svgrepo.com/search/",
    "https://www.flaticon.com/search?word=",
    "https://icons8.com/icons/set/",
    "https://www.iconfinder.com/search?q=",
    "https://www.vecteezy.com/free-vector/",
    "https://www.freepik.com/search?query=",

    # ---- DIY, Home & Garden ----
    "https://www.instructables.com/search/?q=",
    "https://www.doityourself.com/stry/",
    "https://www.familyhandyman.com/search/?q=",
    "https://www.thisoldhouse.com/search?q=",
    "https://www.houzz.com/photos/query/",
    "https://www.apartmenttherapy.com/search?q=",
    "https://www.bhg.com/search?q=",
    "https://www.gardening know how.com/",
    "https://www.gardenersworld.com/search/?q=",
    "https://www.rhs.org.uk/search?query=",
    "https://www.thespruce.com/search?q=",
    "https://www.hunker.com/search?q=",
    "https://www.bob-vila.com/search?q=",
    "https://www.renovationfind.com/search/",

    # ---- Legal & Government ----
    "https://www.law.cornell.edu/search/site/",
    "https://www.justia.com/search?q=",
    "https://scholar.google.com/scholar?as_sdt=6,44&q=",
    "https://casetext.com/search?q=",
    "https://www.courtlistener.com/?q=",
    "https://pacer.gov/search/",
    "https://www.federalregister.gov/search?conditions[term]=",
    "https://www.congress.gov/search?q=",
    "https://www.govinfo.gov/app/search/%7B%22query%22%3A%22",
    "https://www.usa.gov/search/",
    "https://regulations.gov/#search/",
    "https://supremecourt.gov/search.aspx?Search=",
    "https://www.uscis.gov/search-results?q=",
    "https://www.irs.gov/search/?q=",
    "https://www.sec.gov/cgi-bin/srqsb?text=form-type%3D10-K+",

    # ---- Environment & Sustainability ----
    "https://www.epa.gov/search?query=",
    "https://www.greenpeace.org/international/search/?q=",
    "https://www.sierraclub.org/search?q=",
    "https://www.worldwildlife.org/search?q=",
    "https://www.nrdc.org/search?q=",
    "https://www.treepeople.org/search/?q=",
    "https://www.earthjustice.org/search?q=",
    "https://www.climatecentral.org/search?q=",
    "https://www.carbonbrief.org/?s=",
    "https://www.insideclimatenews.org/?s=",
    "https://e360.yale.edu/search?s=",
    "https://www.ensia.com/?s=",
    "https://grist.org/?s=",

    # ---- Podcasts & Audio ----
    "https://podcasts.apple.com/us/search?term=",
    "https://open.spotify.com/search/",
    "https://podcastaddict.com/search#",
    "https://www.listennotes.com/search/?q=",
    "https://www.podchaser.com/search/master/",
    "https://player.fm/search/",
    "https://www.podcast.co/search?q=",
    "https://podbay.fm/search?q=",
    "https://www.podcastrepublic.net/search?keyword=",
    "https://www.stitcher.com/search?q=",
    "https://overcast.fm/search?q=",
    "https://www.iheart.com/search/all/",

    # ---- Jobs & Careers ----
    "https://www.linkedin.com/jobs/search/?keywords=",
    "https://www.indeed.com/jobs?q=",
    "https://www.glassdoor.com/job-listing/search.htm?typedKeyword=",
    "https://www.ziprecruiter.com/jobs-search?search%5Bterms%5D=",
    "https://www.monster.com/jobs/search?q=",
    "https://www.simplyhired.com/search?q=",
    "https://www.careerbuilder.com/jobs?keywords=",
    "https://www.dice.com/jobs?q=",
    "https://angel.co/jobs?query=",
    "https://wellfound.com/jobs?q=",
    "https://www.flexjobs.com/jobs/",
    "https://remote.co/remote-jobs/search/?search_keywords=",
    "https://weworkremotely.com/remote-jobs/search?term=",
    "https://remoteok.com/search?q=",
    "https://himalayas.app/jobs/search?q=",
    "https://www.workingnomads.com/jobs?query=",
    "https://www.usajobs.gov/Search/Results?k=",
    "https://www.idealist.org/en/jobs?q=",

    # ---- Real Estate ----
    "https://www.zillow.com/homes/",
    "https://www.realtor.com/realestateandhomes-search/",
    "https://www.trulia.com/search/",
    "https://www.redfin.com/homes-for-sale/",
    "https://www.homes.com/for-sale/",
    "https://www.century21.com/real-estate/",
    "https://www.coldwellbankerhomes.com/search/",
    "https://www.berkshirehathawayhs.com/search",
    "https://www.compass.com/homes-for-sale/",
    "https://www.loopnet.com/search/commercial-real-estate/",
    "https://www.crexi.com/lease",

    # ---- Kids & Parenting ----
    "https://www.parents.com/search?q=",
    "https://www.babycenter.com/search?q=",
    "https://www.whattoexpect.com/search?q=",
    "https://www.romper.com/search?q=",
    "https://www.fatherly.com/search?q=",
    "https://www.scholastic.com/parents/search.html?search-query=",
    "https://www.pbs.org/kids/search/?q=",
    "https://www.commonsensemedia.org/search/",
    "https://www.understood.org/search?q=",
    "https://kidshealth.org/en/search/",
    "https://www.funbrain.com/search-results/?q=",

    # ---- Fashion & Beauty ----
    "https://www.vogue.com/search?q=",
    "https://www.harpersbazaar.com/search?q=",
    "https://www.elle.com/search?q=",
    "https://www.instyle.com/search?q=",
    "https://www.glamour.com/search?q=",
    "https://www.refinery29.com/en-us/search?q=",
    "https://www.whowhatwear.com/search?q=",
    "https://www.cosmopolitan.com/search?q=",
    "https://www.allure.com/search?q=",
    "https://www.byrdie.com/search?q=",
    "https://www.thecutcut.com/search?q=",
    "https://www.stylecaster.com/search/?q=",
    "https://www.lookbook.nu/search?q=",
    "https://www.polyvore.com/search?query=",

    # ---- Automotive ----
    "https://www.cars.com/search/",
    "https://www.autotrader.com/cars-for-sale/?q=",
    "https://www.carmax.com/cars/all?search=",
    "https://www.cargurus.com/Cars/inventorylisting/viewDetailsFilterViewInventoryListing.action?zip=&distance=100&searchChanged=true&trim=&trim=&drivetrain=&minPrice=&maxPrice=&minMileage=&maxMileage=&transmission=a&startYear=&endYear=&minEngineDisplacement=&maxEngineDisplacement=&bodyTypeGroup=&popularityFilter=CONSUMER_RATED&entitySelectingHelper.selectedEntity=",
    "https://www.edmunds.com/inventory/srp.html?q=",
    "https://www.kbb.com/cars-for-sale/listings/results/?q=",
    "https://www.motortrend.com/search/?q=",
    "https://www.car-and-driver.com/search?q=",
    "https://www.road-track.com/search?q=",
    "https://www.caranddriver.com/search?q=",
    "https://www.topgear.com/search?q=",
    "https://jalopnik.com/search?q=",
    "https://www.autoblog.com/search/?q=",

    # ---- Philosophy & Religion ----
    "https://plato.stanford.edu/search/searcher.py?query=",
    "https://www.iep.utm.edu/?s=",
    "https://www.philosophybasics.com/search.html?q=",
    "https://www.sacred-texts.com/index.htm",
    "https://www.biblegateway.com/quicksearch/?quicksearch=",
    "https://www.blueletterbible.org/search/search.cfm?Criteria=",
    "https://quranx.com/search/?q=",
    "https://www.islamicity.org/search/?q=",
    "https://www.accesstoinsight.org/search.html?q=",
    "https://www.ancient.eu/search/?q=",
    "https://www.britannica.com/topic/philosophy",

    # ---- Language & Linguistics ----
    "https://translate.google.com/?sl=auto&tl=en&text=",
    "https://www.deepl.com/translator#auto/en/",
    "https://reverso.net/translating.aspx?lang=EN&text=",
    "https://context.reverso.net/translation/english-french/",
    "https://www.linguee.com/search?query=",
    "https://forvo.com/search/",
    "https://www.wordreference.com/es/en/translation.asp?spen=",
    "https://www.collinsdictionary.com/search/?dictCode=english&q=",
    "https://www.lexilogos.com/english/english.htm",
    "https://en.wiktionary.org/w/index.php?search=",
    "https://www.etymonline.com/search?q=",
    "https://corpus.byu.edu/",
    "https://www.naclo.org/search/",

    # ---- Pets & Animals ----
    "https://www.petfinder.com/search/",
    "https://www.akc.org/expert-advice/search/?q=",
    "https://www.aspca.org/search/?q=",
    "https://www.hillspet.com/search#q=",
    "https://www.vetstreet.com/search?q=",
    "https://www.mercola.com/sites/articles/archive/pet/",
    "https://www.whole-dog-journal.com/search?q=",
    "https://cattime.com/search?q=",
    "https://www.thesprucepets.com/search?q=",
    "https://www.fishkeepingworld.com/?s=",
    "https://www.reptiles.com/search?q=",
    "https://www.exoticpetvet.com/?s=",

    # ---- Mental Health & Psychology ----
    "https://www.psychologytoday.com/us/therapists",
    "https://www.verywellmind.com/search?q=",
    "https://www.helpguide.org/search?q=",
    "https://www.mentalhealth.org.uk/explore-mental-health/publications?search=",
    "https://www.mind.org.uk/information-support/",
    "https://www.nami.org/Support-Education/",
    "https://www.betterhelp.com/advice/search/?q=",
    "https://www.talkspace.com/blog/search?q=",
    "https://www.psychcentral.com/search?q=",
    "https://www.goodtherapy.org/learn-about-therapy/search?q=",
    "https://www.anxietyandepression.org/search/?q=",
    "https://www.psychologytoday.com/us/blog/search?q=",
    "https://www.additudemag.com/search/?q=",
    "https://www.understood.org/search?q=",
    "https://positivepsychology.com/?s=",
    "https://www.simplypsychology.org/search.html?q=",
    "https://www.apa.org/search?query=",
    "https://www.psychiatry.org/search#q=",

    # ---- History & Archaeology ----
    "https://www.history.com/search#q=",
    "https://www.smithsonianmag.com/search/?q=",
    "https://www.ancient.eu/search/?q=",
    "https://www.historyhit.com/search?q=",
    "https://www.historyextra.com/search/?q=",
    "https://www.britannica.com/search?query=",
    "https://www.worldhistory.org/search/?q=",
    "https://www.archaeology.org/search?q=",
    "https://www.archaeologymag.com/search?q=",
    "https://www.livescience.com/search?q=",
    "https://plato.stanford.edu/search/searcher.py?query=",
    "https://www.jstor.org/action/doBasicSearch?Query=",
    "https://www.loc.gov/search/?q=",
    "https://dp.la/search?q=",
    "https://chroniclingamerica.loc.gov/search/pages/results/?andtext=",
    "https://www.europeana.eu/en/search?query=",
    "https://www.historynet.com/search?q=",
    "https://militaryhistorynow.com/?s=",
    "https://www.nps.gov/search/index.htm?q=",
    "https://www.findagrave.com/memorial/search?q=",

    # ---- Space & Astronomy ----
    "https://www.nasa.gov/search-results/?q=",
    "https://www.space.com/search?searchTerm=",
    "https://earthsky.org/?s=",
    "https://skyandtelescope.org/?s=",
    "https://www.universetoday.com/?s=",
    "https://www.spacenews.com/?s=",
    "https://www.astronomy.com/search?q=",
    "https://www.astronomynow.com/?s=",
    "https://apod.nasa.gov/apod/archivepix.html",
    "https://hubblesite.org/images/gallery",
    "https://www.jpl.nasa.gov/search?q=",
    "https://www.eso.org/public/news/",
    "https://www.planetary.org/search?q=",
    "https://www.spacex.com/updates",
    "https://www.blueorigin.com/news",
    "https://www.rocketlabusa.com/updates/",
    "https://www.isro.gov.in/SearchNews?q=",
    "https://exoplanetarchive.ipac.caltech.edu/cgi-bin/TblView/nph-tblView?app=ExoTbls&config=PS",
    "https://ssd.jpl.nasa.gov/horizons/",

    # ---- Crypto & Web3 ----
    "https://coinmarketcap.com/search/?q=",
    "https://www.coingecko.com/en/search?query=",
    "https://www.coindesk.com/search?q=",
    "https://cointelegraph.com/search?q=",
    "https://decrypt.co/search?s=",
    "https://www.theblock.co/search?q=",
    "https://blockworks.co/search?q=",
    "https://cryptoslate.com/search/?q=",
    "https://ambcrypto.com/?s=",
    "https://beincrypto.com/search/?q=",
    "https://cryptopotato.com/search/?q=",
    "https://www.dextools.io/app/en/pairs",
    "https://etherscan.io/search?f=4&q=",
    "https://solscan.io/search?keyword=",
    "https://polygonscan.com/search?q=",
    "https://www.nftexplorer.app/explore?q=",
    "https://opensea.io/assets?search%5BsortBy%5D=VIEWER_COUNT&search%5Bquery%5D=",
    "https://rarible.com/explore/all?search=",
    "https://www.coinbase.com/explore",
    "https://defillama.com/yields?search=",

    # ---- Maps & Local Discovery ----
    "https://www.google.com/maps/search/",
    "https://www.yelp.com/search?find_desc=",
    "https://foursquare.com/explore?q=",
    "https://www.tripadvisor.com/Search?q=",
    "https://www.openstreetmap.org/search?query=",
    "https://nominatim.openstreetmap.org/search?q=",
    "https://www.mapquest.com/search/result?query=",
    "https://www.here.com/search/",
    "https://www.mapbox.com/search-service",
    "https://www.whereis.com/?q=",
    "https://www.yellowpages.com/search?search_terms=",
    "https://www.whitepages.com/search/FindBusiness?business_search=",
    "https://www.superpages.com/search?business_name=",
    "https://www.manta.com/search?search=",
    "https://www.bbb.org/search?find_text=",
    "https://www.angieslist.com/search.aspx?q=",
    "https://www.thumbtack.com/search#q=",
    "https://www.nextdoor.com/search/",
    "https://patch.com/search?q=",
    "https://www.citysearch.com/search?q=",

    # ---- Marketplace & Classifieds ----
    "https://www.craigslist.org/search/sss?query=",
    "https://www.facebook.com/marketplace/search?query=",
    "https://offerup.com/search/?q=",
    "https://www.mercari.com/search/?keyword=",
    "https://poshmark.com/search?query=",
    "https://www.depop.com/search/?q=",
    "https://vinted.com/catalog?search_text=",
    "https://www.tradesy.com/search/?query=",
    "https://www.thredup.com/p#SearchDept=all&SearchText=",
    "https://www.letgo.com/en-us/q-",
    "https://5miles.com/search?q=",
    "https://www.geebo.com/classifieds/search?search_words=",
    "https://www.listia.com/search?q=",
    "https://www.oodle.com/c/search?q=",
    "https://www.loot4u.com/search?q=",
    "https://swappa.com/listings/search?q=",
    "https://decluttr.com/tech-checker/",
    "https://www.backmarket.com/en-us/search?q=",
    "https://www.gazelle.com/search?q=",

    # ---- Photography & Camera ----
    "https://www.dpreview.com/search?q=",
    "https://www.digitalcameraworld.com/search?q=",
    "https://www.imaging-resource.com/search.htm?q=",
    "https://www.kenrockwell.com/search.htm",
    "https://www.lenstip.com/szukaj.php?szukaj=",
    "https://www.photoreview.com.au/search/?q=",
    "https://www.photographytalk.com/search?q=",
    "https://www.digitalphoto.com.au/search/?q=",
    "https://fstoppers.com/search?q=",
    "https://petapixel.com/search/?q=",
    "https://www.lightstalking.com/search?q=",
    "https://www.ephotozine.com/search/",
    "https://www.bhphotovideo.com/c/search?Ntt=",
    "https://www.adorama.com/l/?searchinfo=",
    "https://www.mpb.com/en-us/used-cameras/?search=",
    "https://www.fredmiranda.com/forum/board/10",
    "https://www.photo.net/forums/search?q=",
    "https://www.pixsy.com/",

    # ---- Music Production & Audio ----
    "https://www.musicradar.com/search?q=",
    "https://www.audiofanzine.com/search/?q=",
    "https://gearspace.com/board/search.php?q=",
    "https://www.kvraudio.com/q.php?q=",
    "https://www.plugin-alliance.com/en/products.html",
    "https://www.splice.com/sounds/search?q=",
    "https://www.loopmasters.com/genres",
    "https://cymatics.fm/",
    "https://www.landr.com/en/blog/search/?q=",
    "https://ask.audio/search?q=",
    "https://www.soundonsound.com/search?q=",
    "https://www.attackmagazine.com/search?q=",
    "https://mixdownmag.com.au/?s=",
    "https://www.pointblankmusicschool.com/search?q=",
    "https://producerhive.com/?s=",

    # ---- Writing & Journalism ----
    "https://www.writersdigest.com/search?q=",
    "https://www.theguardian.com/tone/features?q=",
    "https://lithub.com/search?q=",
    "https://electricliterature.com/search?q=",
    "https://www.theatlantic.com/search/?q=",
    "https://www.newyorker.com/search/q/",
    "https://longreads.com/search/?q=",
    "https://www.narratively.com/search?q=",
    "https://www.aeonmedia.co/search?q=",
    "https://www.granta.com/search/?q=",
    "https://www.believermag.com/search?q=",
    "https://www.guernicamag.com/?s=",
    "https://www.nonfictionwriters.com/search?q=",
    "https://www.copyblogger.com/search/?q=",
    "https://problogger.com/search?q=",
    "https://www.smartpassiveincome.com/search?q=",
    "https://neilpatel.com/search/?q=",

    # ---- Parenting & Baby ----
    "https://www.babycenter.com/search?q=",
    "https://www.whattoexpect.com/search?q=",
    "https://www.thebump.com/search?q=",
    "https://www.parents.com/search?q=",
    "https://www.todaysparent.com/search?q=",
    "https://www.motherandbaby.co.uk/search?q=",
    "https://www.babycentre.co.uk/search?q=",
    "https://www.bounty.com/search?q=",
    "https://www.netmums.com/search?q=",
    "https://www.mumsnet.com/search?q=",
    "https://community.babycenter.com/search?q=",
    "https://www.kellymom.com/?s=",
    "https://www.laleche.org.uk/search?q=",
    "https://www.zerotothree.org/search?q=",
    "https://www.pathways.org/search?q=",

    # ---- Weddings & Events ----
    "https://www.theknot.com/search?q=",
    "https://www.weddingwire.com/search?q=",
    "https://www.brides.com/search?q=",
    "https://www.marthastewartweddings.com/search?q=",
    "https://www.stylemepretty.com/search?q=",
    "https://greenweddingshoes.com/search?q=",
    "https://oncewed.com/search?q=",
    "https://www.100layercake.com/search?q=",
    "https://junebugweddings.com/search?q=",
    "https://www.elizabethannedesigns.com/search?q=",
    "https://www.eventbrite.com/d/",
    "https://www.meetup.com/find/?keywords=",
    "https://10times.com/events?keyword=",
    "https://www.allevents.in/search?q=",
    "https://www.eventful.com/events?q=",

    # ---- Outdoor & Adventure ----
    "https://www.alltrails.com/explore?q=",
    "https://www.hikingproject.com/route/find?q=",
    "https://www.trailforks.com/search/?q=",
    "https://www.mountainproject.com/route-finder",
    "https://www.outdoorproject.com/search?q=",
    "https://www.rei.com/learn/expert-advice/search?q=",
    "https://www.backpacker.com/search?q=",
    "https://www.outsideonline.com/search/?q=",
    "https://gearjunkie.com/?s=",
    "https://www.adventure-journal.com/search?q=",
    "https://www.adventurerous.com/search?q=",
    "https://www.themeoutdoors.com/search?q=",
    "https://www.surfline.com/surf-report/",
    "https://www.magicseaweed.com/forecast/",
    "https://www.windguru.cz/int/",
    "https://www.wunderground.com/forecast/",
    "https://www.mountainweather.com/forecasts/",
    "https://www.avalanche.org/forecasts/",
    "https://www.hikr.org/search/?q=",
    "https://peakbagger.com/search.aspx?q=",

    # ---- Fitness & Bodybuilding ----
    "https://www.bodybuilding.com/content/search.html?q=",
    "https://www.muscleandfitness.com/search?q=",
    "https://www.menshealth.com/fitness/search?q=",
    "https://www.womenshealthmag.com/fitness/search?q=",
    "https://www.shape.com/fitness/search?q=",
    "https://www.runnersworld.com/search/?q=",
    "https://www.bicycling.com/search/?q=",
    "https://www.triathlete.com/search/?q=",
    "https://www.swimswam.com/search?q=",
    "https://www.crossfit.com/essentials",
    "https://www.nerdfitness.com/search?q=",
    "https://www.stronglifts.com/search?q=",
    "https://www.t-nation.com/search?q=",
    "https://www.breakingmuscle.com/search?q=",
    "https://examine.com/search/?q=",
    "https://www.ptonthenet.com/search?q=",
    "https://www.acefitness.org/education-and-resources/lifestyle/exercise-library/",
    "https://www.darebee.com/search.html?q=",

    # ---- Investing & Stock Market ----
    "https://finance.yahoo.com/quote/",
    "https://www.marketwatch.com/search?q=",
    "https://seekingalpha.com/search?q=",
    "https://stockanalysis.com/stocks/",
    "https://finviz.com/screener.ashx?v=111&f=",
    "https://simplywall.st/search?q=",
    "https://www.fool.com/search/solr.aspx?q=",
    "https://www.thestreet.com/search?q=",
    "https://www.barrons.com/search?q=",
    "https://www.zacks.com/stock/quote/",
    "https://www.macrotrends.net/stocks/research",
    "https://roic.ai/search?q=",
    "https://stockanalysis.com/etf/",
    "https://etfdb.com/screener/#page=1",
    "https://www.etf.com/etfanalytics/etf-finder?q=",
    "https://www.portfoliovisualizer.com/backtest-portfolio",
    "https://www.gurufocus.com/term/search?q=",
    "https://www.wisesheets.io/search?q=",
    "https://www.morningstar.com/search?query=",
    "https://www.valueline.com/research/",
    "https://www.ibisworld.com/industries/",
    "https://www.statista.com/search/?q=",

    # ---- AI & Machine Learning ----
    "https://arxiv.org/search/?searchtype=all&query=",
    "https://paperswithcode.com/search?q_meta=&q_type=&q=",
    "https://www.semanticscholar.org/search?q=",
    "https://huggingface.co/models?search=",
    "https://www.kaggle.com/search?q=",
    "https://neptune.ai/blog/search?q=",
    "https://www.deeplearning.ai/search?q=",
    "https://towardsdatascience.com/search?q=",
    "https://machinelearningmastery.com/?s=",
    "https://www.fast.ai/search?q=",
    "https://distill.pub/",
    "https://openai.com/research/",
    "https://ai.googleblog.com/",
    "https://www.microsoft.com/en-us/research/search/?q=",
    "https://research.fb.com/search?q=",
    "https://deepmind.google/research/",
    "https://www.ibm.com/blogs/research/",
    "https://ai.stanford.edu/search?q=",
    "https://bair.berkeley.edu/blog/",
    "https://lilianweng.github.io/",
    "https://www.lesswrong.com/search?query=",
    "https://aligned.ai/research/",

    # ---- Software & SaaS Reviews ----
    "https://www.g2.com/search?query=",
    "https://www.capterra.com/search/?query=",
    "https://www.trustradius.com/search?q=",
    "https://www.softwareadvice.com/software/search?q=",
    "https://www.getapp.com/search?q=",
    "https://alternativeto.net/browse/search/?q=",
    "https://www.slant.co/search#query=",
    "https://stackshare.io/search?q=",
    "https://www.saashub.com/search?q=",
    "https://www.appsumo.com/search/?q=",
    "https://www.producthunt.com/search?q=",
    "https://sourceforge.net/directory/?q=",
    "https://www.cnet.com/search/?q=",
    "https://www.pcmag.com/search?q=",
    "https://www.techradar.com/search?q=",
    "https://www.tomsguide.com/search?q=",
    "https://www.tomsguide.com/reviews",
    "https://www.digitaltrends.com/search/?q=",
    "https://www.techspot.com/search.php?q=",
    "https://www.anandtech.com/search?q=",

    # ---- Cybersecurity & Privacy ----
    "https://www.exploit-db.com/search?q=",
    "https://cve.mitre.org/cgi-bin/cvekey.cgi?keyword=",
    "https://nvd.nist.gov/vuln/search/results?query=",
    "https://www.securityfocus.com/search.html?q=",
    "https://www.darkreading.com/search?q=",
    "https://krebsonsecurity.com/search/",
    "https://www.bleepingcomputer.com/search/?q=",
    "https://www.schneier.com/cgi-bin/mt-search.cgi?search=",
    "https://www.troyhunt.com/search?q=",
    "https://www.haveibeenpwned.com/",
    "https://virustotal.com/gui/home/search",
    "https://www.shodan.io/search?query=",
    "https://censys.io/search?q=",
    "https://urlscan.io/search/#",
    "https://www.abuseipdb.com/check/",
    "https://www.threatminer.org/search.php?q=",
    "https://otx.alienvault.com/browse/global/",
    "https://www.cyberscoop.com/search?q=",
    "https://securityaffairs.com/search?q=",

    # ---- Parenting Teens & Education ----
    "https://www.teenvogue.com/search?q=",
    "https://www.teenink.com/search?q=",
    "https://www.dosomething.org/us/search?q=",
    "https://www.fastweb.com/search?q=",
    "https://www.scholarships.com/search?q=",
    "https://www.petersons.com/college-search",
    "https://www.cappex.com/college-search",
    "https://www.collegevine.com/schools/search",
    "https://bigfuture.collegeboard.org/college-search",
    "https://www.niche.com/colleges/search/",
    "https://www.unigo.com/college_search",
    "https://www.act.org/content/act/en/college-and-career-planning.html",
    "https://www.commonapp.org/explore/colleges",
    "https://gradcafe.com/search?q=",

    # ---- Medicine & Clinical ----
    "https://clinicaltrials.gov/ct2/search/browse?q=",
    "https://www.cochranelibrary.com/search?p_o=0&p_st=0&searchBy=6&searchText=",
    "https://www.uptodate.com/home/content/search?search=",
    "https://emedicine.medscape.com/",
    "https://radiopaedia.org/search?lang=us&q=",
    "https://www.merckmanuals.com/professional/search?q=",
    "https://www.aafp.org/search.html?q=",
    "https://www.nejm.org/search#q=",
    "https://jamanetwork.com/searchresults?q=",
    "https://www.thelancet.com/search?q=",
    "https://bmj.com/search?q=",
    "https://annals.org/aim/searchresults?q=",
    "https://www.mayoclinic.org/diseases-conditions",
    "https://www.clevelandclinic.org/health/search?q=",
    "https://www.hopkinsmedicine.org/search.html?q=",
    "https://stanfordhealthcare.org/search.html?q=",

    # ---- Home Decor & Interior Design ----
    "https://www.houzz.com/photos/query/",
    "https://www.apartmenttherapy.com/search?q=",
    "https://www.bhg.com/search?q=",
    "https://www.housebeautiful.com/search?q=",
    "https://www.architecturaldigest.com/search?q=",
    "https://www.dezeen.com/search/?q=",
    "https://www.designsponge.com/search?q=",
    "https://www.designmilk.com/search?q=",
    "https://www.curbed.com/search?q=",
    "https://www.lonny.com/search?q=",
    "https://www.elledecor.com/search?q=",
    "https://www.mydomaine.com/search?q=",
    "https://freshome.com/search/?q=",
    "https://www.decoraid.com/blog/search?q=",
    "https://www.thespruce.com/search?q=",
    "https://www.roomsketcher.com/blog/search?q=",

    # ---- Gaming ----
    "https://store.steampowered.com/search/?term=",
    "https://www.gog.com/games?genres=&devpub=&system=&price=&sort=bestselling&search=",
    "https://www.igdb.com/search?type=1&q=",
    "https://www.rawg.io/search?q=",
    "https://howlongtobeat.com/games?q=",
    "https://www.metacritic.com/search/game/",
    "https://www.gamespot.com/search/?q=",
    "https://www.ign.com/search?q=",
    "https://www.polygon.com/search?q=",
    "https://www.kotaku.com/search?q=",
    "https://www.pcgamer.com/search/?q=",
    "https://www.eurogamer.net/search/?q=",
    "https://www.rockpapershotgun.com/search?q=",
    "https://www.vg247.com/search?q=",
    "https://www.destructoid.com/search?q=",
    "https://www.giantbomb.com/search/?q=",
    "https://www.neoseeker.com/search/?q=",
    "https://gamefaqs.gamespot.com/search?game=",
    "https://www.speedrun.com/search?q=",
    "https://www.twitch.tv/search?term=",
    "https://www.nexusmods.com/search/?gsearch=",
    "https://www.curseforge.com/search?q=",
    "https://modrinth.com/mods?q=",
    "https://www.pcgamingwiki.com/w/index.php?search=",
    "https://protondb.com/search?q=",

    # ---- Anime & Manga ----
    "https://myanimelist.net/search/all?q=",
    "https://anilist.co/search/anime?search=",
    "https://www.anime-planet.com/anime/all?name=",
    "https://kitsu.app/explore/anime?text=",
    "https://www.crunchyroll.com/search?from=&q=",
    "https://www.funimation.com/search/?q=",
    "https://www.viz.com/search?search=",
    "https://mangaplus.shueisha.co.jp/search_result/",
    "https://www.mangadex.org/search?q=",
    "https://www.webtoons.com/en/search?keyword=",
    "https://mangakakalot.com/search/story/",
    "https://www.readmangato.com/search/story/",
    "https://www.animenewsnetwork.com/search?q=",
    "https://anitrendz.net/polls/search?q=",
    "https://www.animefemale.com/search?q=",

    # ---- Comics & Graphic Novels ----
    "https://www.marvel.com/search?query=",
    "https://www.dccomics.com/search?q=",
    "https://www.comixology.com/search?format=comic&query=",
    "https://www.comicbookplus.com/index.php?cid=search&query=",
    "https://www.comics.org/search/advanced/",
    "https://www.comicvine.gamespot.com/search/?q=",
    "https://leagueofcomicgeeks.com/search?query=",
    "https://www.shortboxed.com/shop/search?q=",
    "https://imagecomics.com/search?q=",
    "https://www.darkhorse.com/search?q=",
    "https://www.boom-studios.com/search?q=",
    "https://tapas.io/search?q=",
    "https://www.webcomicsapp.com/search?q=",

    # ---- Hobbies: Crafts & DIY ----
    "https://www.instructables.com/search/?q=",
    "https://www.ravelry.com/patterns/search#query=",
    "https://www.craftsy.com/search/?q=",
    "https://www.creativebug.com/search?q=",
    "https://www.yarnspirations.com/search?q=",
    "https://www.joann.com/search?q=",
    "https://www.michaels.com/search?q=",
    "https://www.hobbylobby.com/search?query=",
    "https://www.createforless.com/shopping/products.aspx?q=",
    "https://www.dickblick.com/search/?q=",
    "https://www.jerry.art/search?q=",
    "https://www.loveknitting.com/search?q=",
    "https://www.weallsew.com/search?q=",
    "https://www.sewingpatternreview.com/search?q=",
    "https://www.quiltinboard.com/search?q=",

    # ---- Hobbies: Collecting ----
    "https://www.ebay.com/sch/i.html?_nkw=",
    "https://www.heritage auctions.com/search/results/?q=",
    "https://www.sothebys.com/en/search?q=",
    "https://www.christies.com/search?q=",
    "https://www.invaluable.com/search/results/?q=",
    "https://www.liveauctioneers.com/search/?q=",
    "https://www.comc.com/search?q=",
    "https://www.psacard.com/pop/search?q=",
    "https://www.tcgplayer.com/search/all/product?q=",
    "https://www.cardmarket.com/en/Yugioh/Products/Search?searchString=",
    "https://www.pokellector.com/search?q=",
    "https://bulbapedia.bulbagarden.net/w/index.php?search=",
    "https://www.numismaticnews.net/search?q=",
    "https://www.coinworld.com/search?q=",
    "https://www.stampworld.com/search?q=",
    "https://www.mysticstamp.com/Products/search/?q=",
    "https://www.funko.com/search?q=",
    "https://www.sideshow.com/search?q=",

    # ---- Genealogy & Family History ----
    "https://www.ancestry.com/search/?name=",
    "https://www.familysearch.org/en/search/?q=",
    "https://www.myheritage.com/research/catalog/?q=",
    "https://www.findmypast.com/search?q=",
    "https://www.geneanet.org/search/?q=",
    "https://www.geni.com/search?q=",
    "https://www.findagrave.com/memorial/search?q=",
    "https://billiongraves.com/search?q=",
    "https://www.fold3.com/search/#q=",
    "https://www.newspapers.com/search/#query=",
    "https://chroniclingamerica.loc.gov/search/pages/results/?andtext=",
    "https://www.wikitree.com/index.php?search=",
    "https://www.werelate.org/wiki/Special:Search?q=",
    "https://www.rootsweb.com/",
    "https://www.genealogybank.com/search/obituaries/results?q=",

    # ---- Agriculture & Farming ----
    "https://www.extension.org/search?q=",
    "https://www.farmprogress.com/search?q=",
    "https://www.agriculture.com/search?q=",
    "https://www.agweb.com/search?q=",
    "https://www.cropwatch.unl.edu/search?q=",
    "https://www.ams.usda.gov/local-food-directories/farmersmarkets",
    "https://www.eatwild.com/products/searchproducts.html",
    "https://www.localharvest.org/search.jsp?q=",
    "https://www.farmersmarketcoalition.org/programs/farmersmarkets/",
    "https://www.farmaid.org/issues/family-farms/",
    "https://organicfarmer.com/search?q=",
    "https://www.motherearthnews.com/search?q=",
    "https://www.backwoodshome.com/search/?q=",
    "https://rodaleinstitute.org/search?q=",

    # ---- Architecture & Urban Planning ----
    "https://www.archdaily.com/search/all?q=",
    "https://www.dezeen.com/search/?q=",
    "https://www.architectural digest.com/search?q=",
    "https://www.archpaper.com/search?q=",
    "https://www.plataformaarquitectura.cl/cl/search?q=",
    "https://www.architectmagazine.com/search?q=",
    "https://www.architecturalrecord.com/search?q=",
    "https://www.domusweb.it/en/search.html?q=",
    "https://www.curbed.com/search?q=",
    "https://urbanland.uli.org/search?q=",
    "https://www.citylab.com/search?q=",
    "https://www.smartcitiesdive.com/search?q=",
    "https://www.planetizen.com/search?q=",
    "https://www.strongtowns.org/search?q=",

    # ---- Podcasts: Specific Directories ----
    "https://podcastindex.org/search?q=",
    "https://www.podcastrepublic.net/search?keyword=",
    "https://chartable.com/search?q=",
    "https://rephonic.com/search?q=",
    "https://podtail.com/search/?q=",
    "https://www.podparadise.com/search?keyword=",
    "https://podcastguru.io/search?q=",
    "https://www.podcastlounge.com/search?q=",
    "https://goodpods.com/search?q=",
    "https://www.podchaser.com/search/master/",
    "https://podsights.com/search?q=",

    # ---- Video & Streaming ----
    "https://www.youtube.com/results?search_query=",
    "https://vimeo.com/search?q=",
    "https://www.dailymotion.com/search/",
    "https://rumble.com/search/video?q=",
    "https://odysee.com/$/search?q=",
    "https://www.bitchute.com/search/?query=",
    "https://www.peertube.tv/search?search=",
    "https://www.twitch.tv/search?term=",
    "https://www.kick.com/search?q=",
    "https://www.tiktok.com/search?q=",
    "https://www.instagram.com/explore/tags/",
    "https://www.facebook.com/search/top?q=",
    "https://www.snapchat.com/search?q=",
    "https://archive.org/search?query=&mediatype=movies",
    "https://www.plex.tv/watch-free-movies-online/",
    "https://www.crackle.com/search/",
    "https://tubitv.com/search?q=",
    "https://www.pluto.tv/search?q=",
    "https://www.peacocktv.com/search?q=",
    "https://tv.apple.com/search/",

    # ---- Maps: Specialty & Niche ----
    "https://www.peakfinder.com/",
    "https://www.wikiloc.com/trails/search?q=",
    "https://www.gaiagps.com/map/",
    "https://caltopo.com/map.html#",
    "https://maps.stamen.com/",
    "https://felt.com/map/",
    "https://earth.google.com/web/",
    "https://www.usgs.gov/tools/national-map-viewer",
    "https://livingatlas.arcgis.com/en/browse/",
    "https://www.opentopomap.org/",
    "https://maps.nls.uk/os/",
    "https://www.oldmapsonline.org/",
    "https://historicaerials.com/viewer",
    "https://www.davidrumsey.com/",
    "https://maps.lib.utexas.edu/maps/",

    # ---- Nonprofit & Charity ----
    "https://www.charitynavigator.org/search/?q=",
    "https://www.charitywatch.org/ratings-and-metrics/search",
    "https://www.guidestar.org/search",
    "https://candid.org/explore-issues/",
    "https://www.give.org/search?q=",
    "https://www.globalgiving.org/search.html?q=",
    "https://www.gofundme.com/s?q=",
    "https://www.kickstarter.com/discover/advanced?ref=discover_tag&term=",
    "https://www.indiegogo.com/explore/all?q=",
    "https://www.volunteermatch.org/search?q=",
    "https://www.idealist.org/en/search?q=",
    "https://www.catchafire.org/opportunities/list/?q=",

    # ---- Science: Specific Fields ----
    "https://www.chemspider.com/Search.aspx?q=",
    "https://pubchem.ncbi.nlm.nih.gov/#query=",
    "https://www.rcsb.org/search?request=",
    "https://www.ebi.ac.uk/ebisearch/search.ebi?query=",
    "https://www.ncbi.nlm.nih.gov/search/all/?term=",
    "https://www.uniprot.org/uniprotkb?query=",
    "https://www.genome.gov/search-results?term=",
    "https://genesdev.cshlp.org/search?q=",
    "https://www.aps.org/search?q=",
    "https://arxiv.org/search/?searchtype=all&query=",
    "https://www.iop.org/search?q=",
    "https://www.aip.org/search?q=",
    "https://www.agu.org/search?q=",
    "https://agupubs.onlinelibrary.wiley.com/action/doSearch?AllField=",
    "https://www.ams.org/search/publications/search?q=",
    "https://zbmath.org/?q=",
    "https://mathworld.wolfram.com/search/?query=",
    "https://www.ams.org/mathscinet/search/",
    "https://projecteuclid.org/search?q=",
    "https://www.jstor.org/action/doBasicSearch?Query=",

    # ---- Immigration & Visas ----
    "https://www.boundless.com/immigration-resources/search?q=",
    "https://www.nolo.com/search?q=",
    "https://www.uscis.gov/search-results?q=",
    "https://travel.state.gov/content/travel/en/search.html#q=",
    "https://www.immihelp.com/search.html?q=",
    "https://www.visahq.com/search/?q=",
    "https://www.emigrate.co.uk/search?q=",
    "https://www.expat.com/forum/search.php?search_keywords=",
    "https://www.internations.org/search?q=",
    "https://www.expatexchange.com/search?q=",
    "https://www.justlanded.com/search?q=",
    "https://www.expatica.com/search/?q=",

    # ---- Food: International & Cultural ----
    "https://www.196flavors.com/search?q=",
    "https://www.internationalcuisine.com/search?q=",
    "https://www.foodbymars.com/?s=",
    "https://www.marthastewart.com/search?q=",
    "https://cooking.nytimes.com/search?q=",
    "https://www.seriouseats.com/search?q=",
    "https://www.davidlebovitz.com/search?q=",
    "https://www.101cookbooks.com/search/",
    "https://www.pinchofyum.com/search?q=",
    "https://smittenkitchen.com/search?q=",
    "https://www.thekitchn.com/search?q=",
    "https://food52.com/recipes/search?q=",
    "https://www.kingarthurbaking.com/search?q=",
    "https://www.seriouseats.com/recipes",
    "https://www.tasteofhome.com/search?search=",
    "https://www.cookscountry.com/search?q=",
    "https://www.cooksillustrated.com/search?q=",
    "https://www.americastestkitchen.com/search?q=",
    "https://www.finecooking.com/search?q=",
    "https://www.chefsresource.com/search?q=",
]

# ==========================================
# 🏢 MASSIVE HIGH-AUTHORITY SITES LIST
# ==========================================
HIGH_TRUST_SITES = [
    # E-Commerce Window Shopping
    "https://www.amazon.com/b?node=16225009011", 
    "https://www.ebay.com/b/Daily-Deals/bn_7114033402",
    "https://www.bestbuy.com/",
    "https://www.etsy.com/c/home-and-living",
    "https://www.homedepot.com/",

    # News & Finance
    "https://news.ycombinator.com/",
    "https://www.bbc.com/news",
    "https://www.cnn.com/world",
    "https://www.forbes.com/business/",
    "https://www.bloomberg.com/markets",
    "https://www.npr.org/sections/news/",

    # Tech & Programming
    "https://stackoverflow.com/questions",
    "https://github.com/explore",
    "https://www.wired.com/",
    "https://www.theverge.com/",
    "https://techcrunch.com/",

    # Reference & Education
    "https://en.wikipedia.org/wiki/Special:Random",
    "https://www.wikihow.com/Special:Randomizer",
    "https://www.britannica.com/",

    # Forums, Lifestyle, & Hobbies
    "https://www.reddit.com/r/AskReddit/",
    "https://www.reddit.com/r/technology/",
    "https://www.imdb.com/chart/top/", 
    "https://www.goodreads.com/list/show/1.Best_Books_Ever",
    "https://www.allrecipes.com/"
]


async def handle_generic_consent(page: Page, behavior: dict):
    """Clears generic cookie banners found on random web pages."""
    try:
        selectors = [
            "button:has-text('Accept all' i)", "button:has-text('I agree' i)", 
            "button:has-text('Accept Cookies' i)", "button:has-text('Got it' i)",
            "button#onetrust-accept-btn-handler", ".cookie-banner button"
        ]
        for sel in selectors:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=1000):
                await click_humanly(page, btn, behavior)
                await asyncio.sleep(lognormal_delay(800, 2000))
                return
    except Exception:
        pass

async def click_random_visible_link(page: Page, behavior: dict) -> bool:
    """Finds a visually prominent link on the page and clicks it using Fitts's Law."""
    try:
        links = await page.locator("a:visible").all()
        valid_links = []
        for link in links:
            box = await link.bounding_box()
            if box and box["width"] > 10 and box["height"] > 10:
                valid_links.append(link)

        if valid_links:
            target_link = random.choice(valid_links[:15])
            await target_link.scroll_into_view_if_needed()
            await asyncio.sleep(lognormal_delay(1000, 2500))
            await click_humanly(page, target_link, behavior)
            return True
    except Exception as e:
        log.debug(f"Failed to find or click a visible link: {e}")
    
    return False

async def wander_session(page: Page, profile_dict: dict):
    persona_name = profile_dict.get("persona", {}).get("name", "UnknownBot")
    behavior = profile_dict.get("behavior", {})
    
    log.info(f"🌍 [{persona_name}] Starting Web Wander session...")

    # Load referrers dynamically
    all_referrers = load_referrers()

    # Determine probabilities based on available referrers
    modes = ["search", "direct"]
    weights = [0.5, 0.5]
    
    # If we have valid external links, give a 25% chance to do a Referrer Strike
    if all_referrers and len(all_referrers) > 0 and "YourSubreddit" not in all_referrers[0]:
        modes.append("referrer_strike")
        weights = [0.40, 0.35, 0.25] 

    mode = random.choices(modes, weights=weights)[0]

    try:
        if mode == "referrer_strike":
            # ---------------------------------------------------------
            # MODE C: EXTERNAL REFERRER STRIKE (YouTube Algorithm Boost)
            # ---------------------------------------------------------
            target_url = random.choice(all_referrers)
            log.info(f"    🚀 [{persona_name}] Mode C: External Referrer Strike!")
            log.info(f"    🧭 [{persona_name}] Navigating to Referrer: {target_url}")
            
            await page.goto(target_url, timeout=60000, wait_until="domcontentloaded")
            await handle_generic_consent(page, behavior)
            await smart_wait(page)

            # 1. Generate "Time on Page" for the Referrer (Makes the click look incredibly organic)
            log.info(f"    👀 [{persona_name}] Reading the referrer post/article...")
            await human_scroll(page, behavior)
            await idle_reading(page, {**behavior, "read_pause_range": (3, 8)})

            # 2. Hunt for the YouTube Link on the page
            log.info(f"    🔎 [{persona_name}] Searching page for YouTube video link...")
            yt_links = await page.locator("a[href*='youtube.com/watch'], a[href*='youtu.be']").all()
            
            if yt_links:
                target_yt = random.choice(yt_links)
                await target_yt.scroll_into_view_if_needed()
                await asyncio.sleep(random.uniform(1.0, 3.0))
                
                log.info(f"    🖱️ [{persona_name}] Found YouTube link! Clicking through to YouTube...")
                await click_humanly(page, target_yt, behavior)
                await smart_wait(page, timeout=8000)
                
                # 3. Micro-Watch (Retention Signal)
                watch_time = random.uniform(30, 120)
                log.info(f"    📺 [{persona_name}] Arrived at YouTube. Watching for {watch_time:.0f}s to log referrer data.")
                await asyncio.sleep(watch_time)
                
            else:
                log.warning(f"    ⚠️ [{persona_name}] No YouTube links found on the referrer page. Bouncing.")


        elif mode == "search":
            # ---------------------------------------------------------
            # MODE A: AI-Powered Search across random platforms
            # ---------------------------------------------------------
            log.info(f"    🧠 [{persona_name}] Mode A: Third-Party Search Engine")
            
            raw_search_term = await generate_dynamic_search(profile_dict, "Web")
            safe_search_term = urllib.parse.quote_plus(raw_search_term)

            base_url = random.choice(SEARCH_DIRECTORIES)
            target_url = base_url + safe_search_term
            
            log.info(f"    🧭 [{persona_name}] Executing search: {target_url}")
            
            await page.goto(target_url, timeout=60000, wait_until="domcontentloaded")
            await handle_generic_consent(page, behavior)
            await smart_wait(page)

            log.info(f"    👀 [{persona_name}] Reviewing search results...")
            await human_scroll(page, behavior)
            await idle_reading(page, behavior)

            log.info(f"    🖱️ [{persona_name}] Looking for a result to click...")
            if await click_random_visible_link(page, behavior):
                log.info(f"        ✅ [{persona_name}] Clicked a result. Reading destination page...")
                await smart_wait(page)
                await human_scroll(page, behavior)
                await idle_reading(page, behavior)
            else:
                log.warning(f"        ⚠️ [{persona_name}] Couldn't find valid link, staying on results.")

        else:
            # ---------------------------------------------------------
            # MODE B: Direct High-Trust Site Browsing
            # ---------------------------------------------------------
            log.info(f"    🏢 [{persona_name}] Mode B: Direct Authority Browsing")
            
            target_url = random.choice(HIGH_TRUST_SITES)
            log.info(f"    🧭 [{persona_name}] Navigating directly to: {target_url}")
            
            await page.goto(target_url, timeout=60000, wait_until="domcontentloaded")
            await handle_generic_consent(page, behavior)
            await smart_wait(page)

            log.info(f"    👀 [{persona_name}] Scrolling homepage (Loading media & tracking pixels)...")
            await human_scroll(page, behavior)
            await idle_reading(page, behavior)

            log.info(f"    🖱️ [{persona_name}] Looking for an internal link to follow...")
            if await click_random_visible_link(page, behavior):
                log.info(f"        ✅ [{persona_name}] Clicked internal link. Reading next page...")
                await smart_wait(page)
                await human_scroll(page, behavior)
                await idle_reading(page, behavior)
            else:
                log.warning(f"        ⚠️ [{persona_name}] Link wasn't clickable, staying on current page.")

        log.info(f"🎉 [{persona_name}] Web Wander complete!")

    except Exception as e:
        log.error(f"❌ [{persona_name}] Failed to complete wander session: {e}")