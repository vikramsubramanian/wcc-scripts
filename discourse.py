from dotenv import load_dotenv
load_dotenv()

import csv
import datetime
import logging
from typing import Dict, List, Optional, Set
import requests
from config import DISCOURSE as config

logger = logging.getLogger(__name__)

class DiscourseGroupManager:
    """Manages Discourse groups and user membership synchronization."""
    
    def __init__(self):
        self.headers = {
            'Api-Key': config['credentials']['key'],
            'Api-Username': config['credentials']['user'],
        }
        self.base_url = config['url']['host']
        self.current_year = datetime.date.today().year
        self.current_group_name = f"club_members_{self.current_year}"
        self.max_pages = 100  # Safety limit for pagination
        
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make HTTP request with proper error handling."""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = requests.request(method, url, headers=self.headers, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            logger.error(f"Request failed: {method} {url} - {e}")
            raise
    
    def get_discourse_users(self) -> List[Dict]:
        """
        Fetch all active users from Discourse.
        
        Returns:
            List of user dictionaries with id, username, and email
        """
        all_users = []
        page = 0
        
        while page < self.max_pages:
            try:
                response = self._make_request(
                    'GET', 
                    f"/admin/users/list/active.json?page={page}&show_emails=true",
                )
                data = response.json()
                
                # Handle different response formats
                users = data if isinstance(data, list) else data.get('users', [])
                
                if not users:
                    break
                
                # Extract required fields
                for user in users:
                    if 'id' in user and 'username' in user:
                        all_users.append({
                            'id': user['id'],
                            'username': user['username'],
                            'email': user.get('email', '').lower()  # Normalize email case
                        })
                    else:
                        logger.warning(f"User missing required fields: {user}")
                
                page += 1
                
            except requests.RequestException:
                logger.error(f"Failed to fetch users page {page}")
                break
        
        print(all_users[-1])
        logger.info(f"Retrieved {len(all_users)} users")
        return all_users
    
    def get_club_members(self, file_path: str) -> List[Dict]:
        """
        Read club members from CSV file.
        
        Args:
            file_path: Path to the CSV file
            
        Returns:
            List of club member dictionaries
        """
        members = []
        
        try:
            with open(file_path, 'r', newline='', encoding='utf-8') as file:
                reader = csv.reader(file)
                next(reader)  # Skip header row
                
                for row in reader:
                    if len(row) >= 5:  # Ensure we have all required fields
                        members.append({
                            'first': row[0].strip(),
                            'last': row[1].strip(),
                            'email': row[2].strip().lower(),  # Normalize email case
                            'sex': row[3].strip(),
                            'dubs': row[4].strip().lower() == 'true'
                        })
        
        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            raise
        except Exception as e:
            logger.error(f"Error reading CSV file: {e}")
            raise
        
        logger.info(f"Loaded {len(members)} club members")
        return members
    
    def find_matching_users(self, discourse_users: List[Dict], club_members: List[Dict]) -> List[Dict]:
        """
        Find discourse users that match club members by email.
        
        Args:
            discourse_users: List of discourse user dictionaries
            club_members: List of club member dictionaries
            
        Returns:
            List of matched users with additional club member info
        """
        # Create email lookup dictionary for O(1) access
        member_lookup = {member['email']: member for member in club_members}
        # logger.info(f"memberlookup: {member_lookup}")
        # logger.info(f"Discourse: {discourse_users}" )
        matches = []
        for user in discourse_users:
            if user['email'] in member_lookup:
                member = member_lookup[user['email']]
                # Add club member info to user
                user_copy = user.copy()
                user_copy.update({
                    'sex': member['sex'],
                    'dubs': member['dubs'],
                    'first': member['first'],
                    'last': member['last']
                })
                matches.append(user_copy)
        
        logger.info(f"Found {len(matches)} matching users")
        return matches
    
    def get_group(self, group_name: str) -> Optional[Dict]:
        """
        Retrieve group information by name.
        
        Args:
            group_name: Name of the group
            
        Returns:
            Group dictionary or None if not found
        """
        try:
            response = self._make_request('GET', f"/groups/{group_name}.json")
            return response.json()['group']
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    def create_club_members_group(self) -> Dict:
        """Create the current year's club members group."""
        group_config = {
            'name': self.current_group_name,
            'automatic': False,
            'automatic_membership_email_domains': 'waterloocyclingclub.ca',
            'allow_membership_requests': False,
            'allow_unknown_sender_topic_replies': False,
            'public_admission': False,
            'public_exit': False,
            'visibility_level': 3,  # Owner and mods only
            'members_visibility_level': 3,  # Owner and mods only
            'bio_cooked': f'<p>Paid WCC members {self.current_year}</p>',
            'bio_excerpt': f'Paid WCC members {self.current_year}',
            'bio_raw': f'Paid WCC members {self.current_year}',
            'flair_color': '000',
            'flair_icon': 'star',
            'flair_type': 'icon',
            'flair_url': 'star',
            'full_name': f'Club Members {self.current_year}',
            'grant_trust_level': 2,
            'mentionable': False,
            'title': f'Club Member {self.current_year}',
        }
        
        response = self._make_request('POST', '/admin/groups.json', json=group_config)
        return response.json()['basic_group']
    
    def get_group_members(self, group_name: str) -> List[Dict]:
        """
        Get all members of a specific group.
        
        Args:
            group_name: Name of the group
            
        Returns:
            List of group member dictionaries
        """
        try:
            response = self._make_request(
                'GET', 
                f"/groups/{group_name}/members.json",
                params={'limit': 1000}
            )
            return response.json()['members']
        except requests.HTTPError as e:
            logger.error(f"Error getting group membership for {group_name}: {e}")
            raise
    
    def get_users_not_in_group(self, potential_members: List[Dict], group_name: str) -> List[Dict]:
        """
        Find users who should be in a group but aren't.
        
        Args:
            potential_members: List of users who should be in the group
            group_name: Name of the group to check
            
        Returns:
            List of users not in the group
        """
        try:
            current_members = self.get_group_members(group_name)
            current_member_ids = {member['id'] for member in current_members}
            
            return [
                user for user in potential_members 
                if user['id'] not in current_member_ids
            ]
        except Exception as e:
            logger.error(f"Error checking group membership: {e}")
            return potential_members  # Return all if we can't check
    
    def filter_women_members(self, members: List[Dict]) -> List[Dict]:
        """Filter members to only include women who are not 'dubs'."""
        return [
            member for member in members 
            if member['sex'] == 'Female' and not member['dubs']
        ]
    
    def add_users_to_group(self, group_id: str, users: List[Dict]) -> Dict:
        """
        Add users to a group.
        
        Args:
            group_id: ID of the group
            users: List of user dictionaries to add
            
        Returns:
            Response from the API
        """
        if not users:
            return {'usernames': []}
        
        emails = ','.join(user['email'] for user in users)
        payload = {'emails': emails}
        
        response = self._make_request(
            'PUT', 
            f"/groups/{group_id}/members.json",
            json=payload
        )
        return response.json()
    
    def sync_club_members_group(self, csv_file_path: str = "members.csv"):
        """
        Synchronize the club members group with the CSV file.
        
        Args:
            csv_file_path: Path to the members CSV file
        """
        logger.info(f"Starting club members group synchronization for {self.current_group_name}")
        logger.info(f"Using CSV file: {csv_file_path}")
        
        try:
            # Get or create the club members group
            logger.info(f"Looking for existing group: {self.current_group_name}")
            club_group = self.get_group(self.current_group_name)
            
            if not club_group:
                logger.info("Club members group not found, creating new group")
                club_group = self.create_club_members_group()
                logger.info(f"Successfully created group with ID: {club_group['id']}")
            else:
                logger.info(f"Found existing group with ID: {club_group['id']}")
            
            # Find users who should be in the group
            logger.info("Fetching discourse users...")
            discourse_users = self.get_discourse_users()
            logger.info(f"Retrieved {len(discourse_users)} discourse users")
            
            logger.info("Loading club members from CSV...")
            club_members = self.get_club_members(csv_file_path)
            logger.info(f"Loaded {len(club_members)} club members from CSV")
            
            logger.info("Finding matching users between discourse and club members...")
            matching_users = self.find_matching_users(discourse_users, club_members)
            logger.info(f"Found {len(matching_users)} users that exist in both discourse and club membership")
            
            if matching_users:
                logger.debug("Matching users details:")
                for user in matching_users:
                    logger.debug(f"  - {user['username']} ({user['email']}) - {user['first']} {user['last']}")
            
            # Find users not currently in the group
            logger.info(f"Checking current membership of group: {self.current_group_name}")
            users_to_add = self.get_users_not_in_group(matching_users, self.current_group_name)
            logger.info(f"Found {len(users_to_add)} users that need to be added to the group")
            
            if users_to_add:
                logger.info("Users to be added:")
                for user in users_to_add:
                    logger.info(f"  - {user['username']} ({user['email']}) - {user['first']} {user['last']}")
                
                logger.info(f"Adding {len(users_to_add)} users to club members group...")
                result = self.add_users_to_group(club_group['id'], users_to_add)
                
                added_usernames = result.get('usernames', [])
                if added_usernames:
                    logger.info(f"Successfully added {len(added_usernames)} users:")
                    for username in added_usernames:
                        logger.info(f"  ✓ {username}")
                else:
                    logger.warning("No usernames returned in add_users_to_group response")
                
                logger.info("Club members group sync completed successfully")
            else:
                logger.info("No users to add to club members group - all eligible users are already members")
                
        except Exception as e:
            logger.error(f"Error during club members group synchronization: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            raise

    def sync_womens_group(self, csv_file_path: str = "members.csv"):
        """
        Synchronize the women's group with eligible members.
        
        Args:
            csv_file_path: Path to the members CSV file
        """
        womens_group = self.get_group('women-club-members')
        if not womens_group:
            logger.warning("Women's group not found")
            return
        
        # Find eligible women members
        discourse_users = self.get_discourse_users()
        club_members = self.get_club_members(csv_file_path)
        matching_users = self.find_matching_users(discourse_users, club_members)
        eligible_women = self.filter_women_members(matching_users)
        
        # Find women not currently in the group
        women_to_add = self.get_users_not_in_group(eligible_women, 'women-club-members')
        
        if women_to_add:
            logger.info(f"Adding {len(women_to_add)} users to women's group")
            result = self.add_users_to_group(womens_group['id'], women_to_add)
            logger.info(f"Added users: {result.get('usernames', [])}")
        else:
            logger.info("No users to add to women's group")


def setup_logging():
    """Configure logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('discourse.log'),
            logging.StreamHandler()
        ]
    )


def main():
    """Main execution function."""
    setup_logging()
    
    try:
        manager = DiscourseGroupManager()
        
        # Sync club members group
        manager.sync_club_members_group()
        
        # # Sync women's group
        manager.sync_womens_group()
        
        logger.info("Group synchronization completed successfully")
        
    except Exception as e:
        logger.error(f"Error during group synchronization: {e}")
        raise