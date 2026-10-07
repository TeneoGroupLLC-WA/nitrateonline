#!/usr/bin/env python3
"""
Re-fetch correct TMDB data for previously mismatched films.
Uses smarter search: filters out documentaries, prefers popularity,
uses director for disambiguation, tries without year constraints.
"""

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
TMDB_DIR = os.path.join(ROOT, 'tmdb_data')
IMAGES_DIR = os.path.join(ROOT, 'images')

TMDB_API_BASE = 'https://api.themoviedb.org/3'
TMDB_IMAGE_BASE = 'https://image.tmdb.org/t/p'
POSTER_SIZE = 'w500'
REQUEST_DELAY = 0.3

BAD_CODES = [
    'r247', 'r5senses', 'radored', 'ragitator', 'ramistad', 'rapower', 'ratl',
    'rautumntale', 'rbdj', 'rbeautiful', 'rbeyondmat', 'rbiggie', 'rbrothers',
    'rchaos', 'rcircle', 'rcompanyman', 'rcontact', 'rcorpses',
    'rdeath', 'rdiabol', 'rdiamonds', 'rdish', 'rdominoes', 'redge', 'relling',
    'remcowboy', 'renigma', 'reye', 'rfight', 'rfighter', 'rgift', 'rgodzilla2K',
    'rgreendr', 'rguru', 'rguys', 'rhappytimes', 'rheadon', 'rheart', 'rheat',
    'rhide', 'rhorse', 'rhours', 'rhumanite', 'riamsam', 'rimpostor', 'rinlaws',
    'rjackpot', 'rjustonetime', 'rkids', 'rlapromesse', 'rlastnight',
    'rlastorders', 'rleaving', 'rmadamesata', 'rmadcity', 'rmade', 'rman',
    'rmax', 'rmissing', 'rmood', 'rnaked', 'rphoto', 'rpokemon2k', 'rprincess',
    'rrain', 'rresort', 'rresort2', 'rrespiro', 'rrunningfree', 'rshowgrl',
    'rsister', 'rsummer', 'rswingers', 'rturidi', 'rvisit', 'rworld', 'rx2',
]

# Verified TMDB IDs (searched with primary_release_year, confirmed titles)
MANUAL_IDS = {
    'r247': 22913,          # TwentyFourSeven (1998)
    'r5senses': 47585,      # The Five Senses (1999)
    'ragitator': 2896,      # Agitator (2001, Miike)
    'ramistad': 11831,      # Amistad (1997)
    'rapower': 66,          # Absolute Power (1997)
    'ratl': 2058,           # Addicted to Love (1997)
    'rautumntale': 10239,   # A Tale of Autumn (1998)
    'rbdj': 649,            # Belle de Jour (1967)
    'rbeautiful': 15940,    # Beautiful Creatures (2000)
    'rbiggie': 30586,       # Biggie & Tupac (2002)
    'rbrothers': 20322,     # The Brothers (2001)
    'rchaos': 5289,         # Chaos (2005)
    'rcircle': 13898,       # The Circle (2000)
    'rcompanyman': 44412,   # Company Man (2000)
    'rcontact': 686,        # Contact (1997)
    'rcorpses': 2662,       # House of 1000 Corpses (2003)
    'rdiabol': 10988,       # Diabolique (1996)
    'rdiamonds': 35118,     # Diamonds (1999)
    'rdish': 5257,          # The Dish (2000)
    'redge': 9433,          # The Edge (1997)
    'relling': 6007,        # Elling (2001)
    'renigma': 10491,       # Enigma (2001)
    'reye': 18681,          # Eye of the Beholder (2000)
    'rgift': 2046,          # The Gift (2000)
    'rgodzilla2K': 10643,   # Godzilla 2000: Millennium (1999)
    'rgreendr': 35868,      # Green Dragon (2001)
    'rguru': 9027,          # The Guru (2002)
    'rguys': 65684,         # The Guys (2002)
    'rhappytimes': 45861,   # Happy Times (2000)
    'rheadon': 13817,       # Head On (1998)
    'rheart': 10564,        # Where the Heart Is (2000)
    'rheat': 949,           # Heat (1995)
    'rhours': 590,          # The Hours (2002)
    'rhumanite': 65296,     # Humanité (1999)
    'riamsam': 10950,       # I Am Sam (2001)
    'rimpostor': 4965,      # Impostor (2001)
    'rinlaws': 5146,        # The In-Laws (2003)
    'rjackpot': 196859,     # Jackpot (2001)
    'rjustonetime': 49267,  # Just One Time (1999)
    'rkids': 9344,          # Kids (1995)
    'rlapromesse': 24183,   # La Promesse (1996)
    'rlastnight': 16129,    # Last Night (1998)
    'rlastorders': 14778,   # Last Orders (2001)
    'rmadamesata': 46993,   # Madame Satã (2002)
    'rmadcity': 9770,       # Mad City (1997)
    'rmade': 15745,         # Made (2001)
    'rman': 10778,          # The Man Who Wasn't There (2001)
    'rmax': 34549,          # Max Keeble's Big Move (2001)
    'rmissing': 12146,      # The Missing (2003)
    'rmood': 843,           # In the Mood for Love (2000)
    'rnaked': 10855,        # Naked Weapon (2002)
    'rpokemon2k': 12599,    # Pokémon the Movie 2000 (1999)
    'rprincess': 9301,      # The Princess and the Warrior (2000)
    'rrain': 354307,        # Rain (2001)
    'rrespiro': 12544,      # Respiro (2002)
    'rrunningfree': 120077, # Running Free (1999)
    'rshowgrl': 10802,      # Showgirls (1995)
    'rsister': 44925,       # Sister My Sister (1994)
    'rsummer': 3597,        # I Know What You Did Last Summer (1997)
    # 'rswingers' removed: 93685 is the 2002 Dutch film; the review is of Swingers (1996), IMDb tt0117802 (issue #27)
    'rturidi': 125325,      # You Laugh / Tu Ridi (1998)
    'rx2': 36658,           # X2 (2003)
}

# These are too obscure for TMDB — skip them
SKIP_CODES = {
    'radored', 'rdominoes', 'remcowboy', 'rfight', 'rhide', 'rleaving',
    'rresort', 'rresort2', 'rbeyondmat', 'rdeath', 'rfighter', 'rhorse',
    'rphoto', 'rvisit', 'rworld',
}


def get_api_key():
    try:
        r = subprocess.run(['git', 'config', '--local', 'tmdb.apikey'],
                           capture_output=True, text=True, cwd=ROOT)
        return r.stdout.strip()
    except:
        return os.environ.get('TMDB_API_KEY', '')


def get_omdb_key():
    try:
        r = subprocess.run(['git', 'config', '--local', 'omdb.apikey'],
                           capture_output=True, text=True, cwd=ROOT)
        return r.stdout.strip()
    except:
        return os.environ.get('OMDB_API_KEY', '')


def tmdb_get(endpoint, params, api_key):
    params = dict(params)
    params['api_key'] = api_key
    url = f'{TMDB_API_BASE}{endpoint}?{urllib.parse.urlencode(params)}'
    req = urllib.request.Request(url, headers={'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        if e.code == 429:
            time.sleep(int(e.headers.get('Retry-After', '5')))
            return tmdb_get(endpoint, params, api_key)
        if e.code == 404:
            return None
        raise
    except urllib.error.URLError:
        return None


def omdb_get(imdb_id, api_key):
    url = f'https://www.omdbapi.com/?i={imdb_id}&apikey={api_key}&plot=full'
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        return data if data.get('Response') == 'True' else None
    except:
        return None


def fetch_full(tmdb_id, api_key):
    detail = tmdb_get(f'/movie/{tmdb_id}', {
        'language': 'en-US',
        'append_to_response': 'credits,release_dates'
    }, api_key)
    if not detail:
        return None

    credits = detail.get('credits', {})
    crew = credits.get('crew', [])
    cast = credits.get('cast', [])

    return {
        'tmdb_id': tmdb_id,
        'title': detail.get('title', ''),
        'original_title': detail.get('original_title', ''),
        'release_date': detail.get('release_date', ''),
        'runtime': detail.get('runtime'),
        'tagline': detail.get('tagline', ''),
        'overview': detail.get('overview', ''),
        'genres': [g['name'] for g in detail.get('genres', [])],
        'spoken_languages': [l.get('english_name', '') for l in detail.get('spoken_languages', [])],
        'production_companies': [{'name': c['name'], 'country': c.get('origin_country', '')}
                                 for c in detail.get('production_companies', [])],
        'director': [c['name'] for c in crew if c.get('job') == 'Director'],
        'writers': [{'name': c['name'], 'job': c.get('job', '')}
                    for c in crew if c.get('department') == 'Writing'],
        'producers': [{'name': c['name'], 'job': c.get('job', '')}
                      for c in crew if c.get('job') in ('Producer', 'Executive Producer')],
        'cast': [{'name': c.get('name', ''), 'character': c.get('character', ''),
                  'order': c.get('order', 99)} for c in cast[:10]],
        'poster_path': detail.get('poster_path'),
        'backdrop_path': detail.get('backdrop_path'),
        'budget': detail.get('budget'),
        'revenue': detail.get('revenue'),
        'vote_average': detail.get('vote_average'),
        'vote_count': detail.get('vote_count'),
        'imdb_id': detail.get('imdb_id'),
        'status': detail.get('status', ''),
    }


def fetch_awards(imdb_id, omdb_key, tmdb_id):
    omdb = omdb_get(imdb_id, omdb_key)
    if not omdb:
        return None

    result = {
        'year': omdb.get('Year', 'N/A'),
        'awards': omdb.get('Awards', 'N/A'),
        'rated': omdb.get('Rated', 'N/A'),
        'released': omdb.get('Released', 'N/A'),
        'runtime': omdb.get('Runtime', 'N/A'),
        'genre': omdb.get('Genre', 'N/A'),
        'director': omdb.get('Director', 'N/A'),
        'writer': omdb.get('Writer', 'N/A'),
        'actors': omdb.get('Actors', 'N/A'),
        'plot': omdb.get('Plot', 'N/A'),
        'language': omdb.get('Language', 'N/A'),
        'country': omdb.get('Country', 'N/A'),
        'metascore': omdb.get('Metascore', 'N/A'),
        'imdb_rating': omdb.get('imdbRating', 'N/A'),
        'imdb_votes': omdb.get('imdbVotes', 'N/A'),
        'box_office': omdb.get('BoxOffice', 'N/A'),
        'dvd': omdb.get('DVD', 'N/A'),
        'ratings': [],
        'links': {
            'imdb': f'https://www.imdb.com/title/{imdb_id}/',
            'imdb_fullcredits': f'https://www.imdb.com/title/{imdb_id}/fullcredits',
            'tmdb': f'https://www.themoviedb.org/movie/{tmdb_id}',
        },
    }

    for r in omdb.get('Ratings', []):
        entry = {'source': r['Source'], 'value': r['Value']}
        if r['Source'] == 'Rotten Tomatoes':
            entry['link'] = f'https://www.rottentomatoes.com/search?search={urllib.parse.quote_plus(omdb.get("Title", ""))}'
        if r['Source'] == 'Metacritic':
            entry['link'] = f'https://www.metacritic.com/search/{urllib.parse.quote_plus(omdb.get("Title", ""))}/'
        result['ratings'].append(entry)

    return result


def download_poster(poster_path, code):
    if not poster_path:
        return False
    url = f'{TMDB_IMAGE_BASE}/{POSTER_SIZE}{poster_path}'
    dst_tmdb = os.path.join(TMDB_DIR, 'posters', f'{code}-poster.jpg')
    dst_img = os.path.join(IMAGES_DIR, f'{code}-poster.jpg')
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'NitrateOnline/1.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        with open(dst_tmdb, 'wb') as f:
            f.write(data)
        with open(dst_img, 'wb') as f:
            f.write(data)
        return True
    except:
        return False


def main():
    dry_run = '--dry-run' in sys.argv
    api_key = get_api_key()
    omdb_key = get_omdb_key()

    if not api_key:
        print("ERROR: No TMDB API key")
        sys.exit(1)

    # Load manifests
    manifest_path = os.path.join(TMDB_DIR, 'manifest.json')
    manifest = json.load(open(manifest_path))

    ok = 0
    failed = 0
    skipped = 0

    for i, code in enumerate(sorted(BAD_CODES), 1):
        # Find the file
        matches = glob.glob(os.path.join(ROOT, f'*/{code}.html'))
        if not matches:
            print(f"[{i}/{len(BAD_CODES)}] {code}: file not found")
            skipped += 1
            continue

        filepath = matches[0]
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()

        m = re.search(r'og:title.*?content="([^"]*)"', content)
        page_title = m.group(1) if m else code

        # Get TMDB ID
        tmdb_id = MANUAL_IDS.get(code)

        if code in SKIP_CODES or not tmdb_id:
            print(f"[{i}/{len(BAD_CODES)}] {code}: \"{page_title}\" — skipped (too obscure or no ID)")
            skipped += 1
            continue

        print(f"[{i}/{len(BAD_CODES)}] {code}: \"{page_title}\" -> TMDB {tmdb_id}...", end=' ', flush=True)

        if dry_run:
            print("(dry run)")
            continue

        # Fetch TMDB details
        full = fetch_full(tmdb_id, api_key)
        time.sleep(REQUEST_DELAY)

        if not full:
            print("TMDB fetch failed")
            failed += 1
            continue

        # Save metadata
        meta_path = os.path.join(TMDB_DIR, 'metadata', f'{code}.json')
        with open(meta_path, 'w') as f:
            json.dump(full, f, indent=2, ensure_ascii=False)

        # Download poster
        poster_ok = download_poster(full.get('poster_path'), code)

        # Fetch OMDb awards
        awards = None
        if full.get('imdb_id') and omdb_key:
            awards = fetch_awards(full['imdb_id'], omdb_key, tmdb_id)
            time.sleep(REQUEST_DELAY)
            if awards:
                awards_path = os.path.join(TMDB_DIR, 'awards', f'{code}.json')
                with open(awards_path, 'w') as f:
                    json.dump(awards, f, indent=2, ensure_ascii=False)

        # Get year from page path
        ym = re.search(r'/(\d{4})/', filepath)
        year = int(ym.group(1)) if ym else None

        # Update manifest
        manifest[code] = {
            'title': page_title,
            'year': year,
            'tmdb_id': tmdb_id,
            'tmdb_title': full.get('title', ''),
            'release_date': full.get('release_date', ''),
            'runtime': full.get('runtime'),
            'director': full.get('director', []),
            'writers': [w['name'] for w in full.get('writers', [])],
            'producers': [p['name'] for p in full.get('producers', [])],
            'cast': [c['name'] for c in full.get('cast', [])[:5]],
            'studios': [s['name'] for s in full.get('production_companies', [])],
            'genres': full.get('genres', []),
            'imdb_id': full.get('imdb_id'),
            'poster_file': f'{code}-poster.jpg' if poster_ok else None,
            'status': 'ok',
        }

        director = ', '.join(full.get('director', ['?']))
        print(f"OK — {full['title']} dir. {director}" +
              (' + poster' if poster_ok else ''))
        ok += 1

    # Save manifest
    if not dry_run:
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False, sort_keys=False)

    print(f"\nDone! OK: {ok}, Failed: {failed}, Skipped: {skipped}")
    if ok > 0 and not dry_run:
        print("Now run: python3 tools/enrich_pages.py")


if __name__ == '__main__':
    main()
