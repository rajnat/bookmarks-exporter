from dotenv import load_dotenv
import tweepy
import json
import os
from notion_client import Client
from datetime import datetime
from typing import List, Dict, Set
import pickle

# Load environment variables from .env file
load_dotenv()

class BookmarkTransfer:
    def _init_(self, x_api_key: str, x_api_secret: str, 
                 x_access_token: str, x_access_token_secret: str,
                 notion_token: str, notion_database_id: str):
        """Initialize with API credentials for both X and Notion."""
        # X API setup
        auth = tweepy.OAuthHandler(x_api_key, x_api_secret)
        auth.set_access_token(x_access_token, x_access_token_secret)
        self.x_client = tweepy.API(auth)
        
        # Notion API setup
        self.notion = Client(auth=notion_token)
        self.database_id = notion_database_id
        
        # Initialize processed bookmarks set
        self.processed_bookmarks_file = 'processed_bookmarks.pkl'
        self.processed_bookmarks = self.load_processed_bookmarks()

    def load_processed_bookmarks(self) -> Set[str]:
        """Load the set of already processed bookmark IDs."""
        try:
            if os.path.exists(self.processed_bookmarks_file):
                with open(self.processed_bookmarks_file, 'rb') as f:
                    return pickle.load(f)
        except Exception as e:
            print(f"Error loading processed bookmarks: {str(e)}")
        return set()

    def save_processed_bookmarks(self):
        """Save the set of processed bookmark IDs."""
        try:
            with open(self.processed_bookmarks_file, 'wb') as f:
                pickle.dump(self.processed_bookmarks, f)
        except Exception as e:
            print(f"Error saving processed bookmarks: {str(e)}")

    def get_existing_bookmark_urls(self) -> Set[str]:
        """Get all bookmark URLs already in Notion database."""
        existing_urls = set()
        try:
            # Query the Notion database
            response = self.notion.databases.query(
                database_id=self.database_id
            )
            
            # Extract URLs from existing pages
            for page in response['results']:
                if 'URL' in page['properties']:
                    url = page['properties']['URL'].get('url')
                    if url:
                        existing_urls.add(url)
            
            return existing_urls
        except Exception as e:
            print(f"Error fetching existing bookmarks from Notion: {str(e)}")
            return set()

    def get_bookmarks(self) -> List[Dict]:
        """Fetch bookmarks from X account."""
        bookmarks = []
        try:
            existing_urls = self.get_existing_bookmark_urls()
            
            # Get bookmarks using Tweepy
            for bookmark in tweepy.Cursor(self.x_client.get_bookmarks).items():
                bookmark_url = f"https://twitter.com/user/status/{bookmark.id}"
                
                # Skip if already processed or exists in Notion
                if (str(bookmark.id) in self.processed_bookmarks or 
                    bookmark_url in existing_urls):
                    continue
                
                bookmark_data = {
                    'id': str(bookmark.id),
                    'text': bookmark.text,
                    'url': bookmark_url,
                    'author': bookmark.user.screen_name,
                    'created_at': bookmark.created_at,
                    'bookmark_data': {
                        'likes': bookmark.favorite_count,
                        'retweets': bookmark.retweet_count
                    }
                }
                bookmarks.append(bookmark_data)
            
            return bookmarks
        except Exception as e:
            print(f"Error fetching bookmarks from X: {str(e)}")
            return []

    def create_notion_page(self, bookmark: Dict) -> bool:
        """Create a new page in Notion database for a bookmark."""
        try:
            self.notion.pages.create(
                parent={"database_id": self.database_id},
                properties={
                    "Title": {
                        "title": [
                            {
                                "text": {
                                    "content": bookmark['text'][:100] + "..."
                                }
                            }
                        ]
                    },
                    "URL": {
                        "url": bookmark['url']
                    },
                    "Author": {
                        "rich_text": [
                            {
                                "text": {
                                    "content": bookmark['author']
                                }
                            }
                        ]
                    },
                    "Date": {
                        "date": {
                            "start": bookmark['created_at'].isoformat()
                        }
                    },
                    "Engagement": {
                        "rich_text": [
                            {
                                "text": {
                                    "content": f"♥ {bookmark['bookmark_data']['likes']} | RT {bookmark['bookmark_data']['retweets']}"
                                }
                            }
                        ]
                    }
                }
            )
            return True
        except Exception as e:
            print(f"Error creating Notion page for bookmark: {str(e)}")
            return False

    def transfer_bookmarks(self) -> None:
        """Main function to transfer bookmarks from X to Notion."""
        print("Starting bookmark transfer...")
        
        # Get new bookmarks from X
        bookmarks = self.get_bookmarks()
        print(f"Found {len(bookmarks)} new bookmarks")
        
        # Transfer each new bookmark to Notion
        successful_transfers = 0
        for i, bookmark in enumerate(bookmarks, 1):
            print(f"Transferring bookmark {i}/{len(bookmarks)}")
            if self.create_notion_page(bookmark):
                self.processed_bookmarks.add(bookmark['id'])
                successful_transfers += 1
        
        # Save the updated set of processed bookmarks
        self.save_processed_bookmarks()
        
        print(f"Transfer complete! Successfully transferred {successful_transfers} new bookmarks.")

def check_environment_variables():
    """Check if all required environment variables are set."""
    required_vars = [
        'X_API_KEY',
        'X_API_SECRET',
        'X_ACCESS_TOKEN',
        'X_ACCESS_TOKEN_SECRET',
        'NOTION_TOKEN',
        'NOTION_DATABASE_ID'
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print("Error: The following required environment variables are missing:")
        for var in missing_vars:
            print(f"- {var}")
        return False
    return True

def main():
    # Check environment variables
    if not check_environment_variables():
        return
    
    # Get credentials from environment variables
    x_credentials = {
        'api_key': os.getenv('X_API_KEY'),
        'api_secret': os.getenv('X_API_SECRET'),
        'access_token': os.getenv('X_ACCESS_TOKEN'),
        'access_token_secret': os.getenv('X_ACCESS_TOKEN_SECRET')
    }
    
    notion_credentials = {
        'token': os.getenv('NOTION_TOKEN'),
        'database_id': os.getenv('NOTION_DATABASE_ID')
    }
    
    try:
        # Initialize and run transfer
        transfer = BookmarkTransfer(
            x_api_key=x_credentials['api_key'],
            x_api_secret=x_credentials['api_secret'],
            x_access_token=x_credentials['access_token'],
            x_access_token_secret=x_credentials['access_token_secret'],
            notion_token=notion_credentials['token'],
            notion_database_id=notion_credentials['database_id']
        )
        
        transfer.transfer_bookmarks()
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if _name_ == "_main_":
    main()