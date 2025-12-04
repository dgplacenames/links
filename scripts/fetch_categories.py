#!/usr/bin/env python3
"""
Fetch all subcategories from Wikimedia Commons Orkney Islands category
and save to a hierarchical JSON structure.
"""

import requests
import json
import time
from datetime import datetime
from pathlib import Path

BASE_URL = "https://commons.wikimedia.org/w/api.php"
MAX_DEPTH = 10

def fetch_subcategories(category_name):
    """Fetch all subcategories for a given category."""
    params = {
        'action': 'query',
        'list': 'categorymembers',
        'cmtitle': f'Category:{category_name}',
        'cmtype': 'subcat',
        'cmlimit': '500',
        'format': 'json'
    }
    
    subcats = []
    
    while True:
        try:
            response = requests.get(BASE_URL, params=params, timeout=30)
            response.raise_for_status()  # Raise error for bad status codes
            
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching subcategories for {category_name}: {e}")
            print(f"Response status: {response.status_code if response else 'No response'}")
            print(f"Response text: {response.text[:200] if response else 'No response'}")
            return []
        except ValueError as e:
            print(f"JSON decode error for {category_name}: {e}")
            print(f"Response text: {response.text[:200]}")
            return []
        
        if 'query' in data and 'categorymembers' in data['query']:
            for cat in data['query']['categorymembers']:
                subcats.append(cat['title'].replace('Category:', ''))
        
        # Check for continuation
        if 'continue' not in data:
            break
        params['cmcontinue'] = data['continue']['cmcontinue']
        
        # Be nice to the API
        time.sleep(0.1)
    
    return subcats

def fetch_file_count(category_name):
    """Fetch the number of files in a category."""
    params = {
        'action': 'query',
        'titles': f'Category:{category_name}',
        'prop': 'categoryinfo',
        'format': 'json'
    }
    
    try:
        response = requests.get(BASE_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching file count for {category_name}: {e}")
        return 0
    except ValueError as e:
        print(f"JSON decode error for file count {category_name}: {e}")
        return 0
    
    if 'query' in data and 'pages' in data['query']:
        page = list(data['query']['pages'].values())[0]
        if 'categoryinfo' in page:
            return page['categoryinfo'].get('files', 0)
    
    return 0

def build_category_tree(parent_category, level=1, max_level=10, visited=None, file_counts=None):
    """Recursively build a category tree with file counts."""
    if visited is None:
        visited = set()
    if file_counts is None:
        file_counts = {}
    
    if parent_category in visited or level > max_level:
        return None
    
    visited.add(parent_category)
    print(f"{'  ' * (level-1)}Fetching: {parent_category}")
    
    subcats = fetch_subcategories(parent_category)
    
    # Get file count for this category
    file_count = fetch_file_count(parent_category)
    file_counts[parent_category] = file_count
    time.sleep(0.1)  # Be nice to the API
    
    if not subcats:
        return None
    
    # Sort alphabetically
    subcats.sort()
    
    result = []
    for subcat in subcats:
        cat_data = {
            'name': subcat,
            'level': level,
            'files': 0  # Will be updated
        }
        
        # Recursively get children
        children = build_category_tree(subcat, level + 1, max_level, visited, file_counts)
        if children:
            cat_data['children'] = children
        
        result.append(cat_data)
    
    return result

def calculate_total_files(tree, file_counts):
    """Calculate total files including all subcategories."""
    if not tree:
        return {}
    
    totals = {}
    
    def recurse(node):
        name = node['name']
        # Start with direct files
        total = file_counts.get(name, 0)
        
        # Add files from all children
        if 'children' in node:
            for child in node['children']:
                total += recurse(child)
        
        totals[name] = total
        return total
    
    for node in tree:
        recurse(node)
    
    return totals

def flatten_category_tree(tree, level=1, total_files=None):
    """Flatten the tree into a simple list with levels and file counts."""
    result = []
    
    if not tree:
        return result
    
    for cat in tree:
        result.append({
            'name': cat['name'],
            'level': level,
            'files': total_files.get(cat['name'], 0) if total_files else 0
        })
        
        if 'children' in cat:
            result.extend(flatten_category_tree(cat['children'], level + 1, total_files))
    
    return result

def main():
    print("=" * 60)
    print("Fetching Orkney Islands categories from Wikimedia Commons")
    print("=" * 60)
    
    # Build the tree and collect file counts
    file_counts = {}
    tree = build_category_tree('Orkney Islands', level=1, max_level=MAX_DEPTH, file_counts=file_counts)
    
    # Calculate total files including subcategories
    print("\nCalculating total file counts...")
    total_files = calculate_total_files(tree, file_counts)
    
    # Flatten the tree
    flat_list = flatten_category_tree(tree, level=1, total_files=total_files)
    
    # Prepare output
    output = {
        'updated': datetime.utcnow().isoformat() + 'Z',
        'root_category': 'Orkney Islands',
        'total_categories': len(flat_list),
        'max_depth': MAX_DEPTH,
        'categories': flat_list
    }
    
    # Ensure data directory exists
    data_dir = Path('data')
    data_dir.mkdir(exist_ok=True)
    
    # Write to file
    output_file = data_dir / 'orkney-categories.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print("=" * 60)
    print(f"Success! Found {len(flat_list)} categories")
    print(f"Saved to: {output_file}")
    print("=" * 60)

if __name__ == '__main__':
    main()
