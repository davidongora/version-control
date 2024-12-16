import os
import json
import hashlib
import shutil
import fnmatch
from typing import List, Dict, Optional

class Repository:
    def __init__(self, path: str):
        """
        Initialize a new repository or open an existing one.
        
        :param path: Path to the repository directory
        """
        self.path = os.path.abspath(path)
        self.repo_dir = os.path.join(path, '.gitclone')
        
        if not os.path.exists(self.repo_dir):
            self._initialize_repo()
        
        self.current_branch = self._get_current_branch()
    
    def _initialize_repo(self):
        """
        Create the repository structure and initial files.
        """
        os.makedirs(self.repo_dir)
        os.makedirs(os.path.join(self.repo_dir, 'objects'))
        os.makedirs(os.path.join(self.repo_dir, 'refs', 'heads'))
        
        # Create initial branch
        with open(os.path.join(self.repo_dir, 'HEAD'), 'w') as f:
            f.write('ref: refs/heads/main')
        
        # Create initial branch file
        with open(os.path.join(self.repo_dir, 'refs', 'heads', 'main'), 'w') as f:
            f.write('')
        
        # Create staging area
        with open(os.path.join(self.repo_dir, 'index'), 'w') as f:
            json.dump([], f)
        
        # Create .gitignore
        with open(os.path.join(self.repo_dir, 'ignore'), 'w') as f:
            f.write('.gitclone\n')
    
    def _get_current_branch(self) -> str:
        """
        Get the current active branch.
        
        :return: Current branch name
        """
        with open(os.path.join(self.repo_dir, 'HEAD'), 'r') as f:
            return f.read().split('/')[-1].strip()
    
    def _should_ignore(self, path: str) -> bool:
        """
        Check if a file should be ignored based on .gitignore patterns.
        
        :param path: Path to the file
        :return: True if file should be ignored, False otherwise
        """
        relative_path = os.path.relpath(path, self.path)
        
        # Read ignore patterns
        try:
            with open(os.path.join(self.repo_dir, 'ignore'), 'r') as f:
                ignore_patterns = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            ignore_patterns = []
        
        # Check against ignore patterns
        for pattern in ignore_patterns:
            if fnmatch.fnmatch(relative_path, pattern):
                return True
        
        return False
    
    def add(self, files: List[str]):
        """
        Stage files for commit.
        
        :param files: List of file paths to stage
        """
        # Read existing index
        with open(os.path.join(self.repo_dir, 'index'), 'r') as f:
            index = json.load(f)
        
        for file in files:
            full_path = os.path.join(self.path, file)
            
            # Check if file exists and is not ignored
            if not os.path.exists(full_path):
                print(f"Error: {file} does not exist")
                continue
            
            if self._should_ignore(full_path):
                print(f"Skipping ignored file: {file}")
                continue
            
            # Compute file hash
            with open(full_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            
            # Store file object
            object_path = os.path.join(self.repo_dir, 'objects', file_hash)
            shutil.copy(full_path, object_path)
            
            # Update index
            index_entry = {
                'path': file,
                'hash': file_hash
            }
            
            # Remove existing entry if exists
            index = [entry for entry in index if entry['path'] != file]
            index.append(index_entry)
        
        # Write updated index
        with open(os.path.join(self.repo_dir, 'index'), 'w') as f:
            json.dump(index, f, indent=2)
        
        print(f"Added {len(files)} file(s) to staging area")
    
    def commit(self, message: str):
        """
        Create a commit with staged files.
        
        :param message: Commit message
        """
        # Read index
        with open(os.path.join(self.repo_dir, 'index'), 'r') as f:
            index = json.load(f)
        
        if not index:
            print("No changes to commit")
            return
        
        # Create commit object
        commit_hash = hashlib.sha256(message.encode()).hexdigest()
        commit_path = os.path.join(self.repo_dir, 'objects', commit_hash)
        
        commit_data = {
            'message': message,
            'timestamp': os.path.getctime(commit_path) if os.path.exists(commit_path) else os.time(),
            'parent': self._get_last_commit(),
            'files': index
        }
        
        # Write commit object
        with open(commit_path, 'w') as f:
            json.dump(commit_data, f, indent=2)
        
        # Update branch reference
        branch_path = os.path.join(self.repo_dir, 'refs', 'heads', self.current_branch)
        with open(branch_path, 'w') as f:
            f.write(commit_hash)
        
        # Clear index
        with open(os.path.join(self.repo_dir, 'index'), 'w') as f:
            json.dump([], f)
        
        print(f"Committed {len(index)} changes: {message}")
    
    def _get_last_commit(self) -> Optional[str]:
        """
        Get the hash of the last commit on the current branch.
        
        :return: Commit hash or None if no previous commits
        """
        branch_path = os.path.join(self.repo_dir, 'refs', 'heads', self.current_branch)
        
        try:
            with open(branch_path, 'r') as f:
                return f.read().strip()
        except FileNotFoundError:
            return None
    
    def log(self):
        """
        Display commit history.
        """
        current_commit = self._get_last_commit()
        
        while current_commit:
            commit_path = os.path.join(self.repo_dir, 'objects', current_commit)
            
            try:
                with open(commit_path, 'r') as f:
                    commit_data = json.load(f)
                
                print(f"Commit: {current_commit}")
                print(f"Message: {commit_data['message']}")
                print(f"Timestamp: {commit_data['timestamp']}")
                print(f"Files: {[file['path'] for file in commit_data['files']]}")
                print("---")
                
                current_commit = commit_data.get('parent')
            except FileNotFoundError:
                break
    
    def branch(self, branch_name: str):
        """
        Create a new branch from the current branch.
        
        :param branch_name: Name of the new branch
        """
        current_commit = self._get_last_commit()
        
        # Create branch reference
        branch_path = os.path.join(self.repo_dir, 'refs', 'heads', branch_name)
        with open(branch_path, 'w') as f:
            f.write(current_commit or '')
        
        print(f"Created branch: {branch_name}")
    
    def checkout(self, branch_name: str):
        """
        Switch to a different branch.
        
        :param branch_name: Name of the branch to checkout
        """
        branch_path = os.path.join(self.repo_dir, 'refs', 'heads', branch_name)
        
        if not os.path.exists(branch_path):
            print(f"Branch {branch_name} does not exist")
            return
        
        # Update HEAD
        with open(os.path.join(self.repo_dir, 'HEAD'), 'w') as f:
            f.write(f'ref: refs/heads/{branch_name}')
        
        self.current_branch = branch_name
        print(f"Switched to branch: {branch_name}")
    
    def diff(self, branch1: str, branch2: str):
        """
        Show differences between two branches.
        
        :param branch1: First branch name
        :param branch2: Second branch name
        """
        branch1_commit = self._get_branch_last_commit(branch1)
        branch2_commit = self._get_branch_last_commit(branch2)
        
        if not branch1_commit or not branch2_commit:
            print("One or both branches have no commits")
            return
        
        branch1_path = os.path.join(self.repo_dir, 'objects', branch1_commit)
        branch2_path = os.path.join(self.repo_dir, 'objects', branch2_commit)
        
        with open(branch1_path, 'r') as f:
            branch1_data = json.load(f)
        
        with open(branch2_path, 'r') as f:
            branch2_data = json.load(f)
        
        branch1_files = {file['path']: file['hash'] for file in branch1_data['files']}
        branch2_files = {file['path']: file['hash'] for file in branch2_data['files']}
        
        print(f"Diff between {branch1} and {branch2}:")
        
        # Find added, removed, and modified files
        for path in set(list(branch1_files.keys()) + list(branch2_files.keys())):
            if path not in branch1_files:
                print(f"Added: {path}")
            elif path not in branch2_files:
                print(f"Removed: {path}")
            elif branch1_files[path] != branch2_files[path]:
                print(f"Modified: {path}")
    
    def _get_branch_last_commit(self, branch_name: str) -> Optional[str]:
        """
        Get the last commit hash for a specific branch.
        
        :param branch_name: Name of the branch
        :return: Commit hash or None if no commits
        """
        branch_path = os.path.join(self.repo_dir, 'refs', 'heads', branch_name)
        
        try:
            with open(branch_path, 'r') as f:
                return f.read().strip()
        except FileNotFoundError:
            return None
    
    def clone(self, destination: str):
        """
        Clone the repository to a new location.
        
        :param destination: Path to clone the repository
        """
        shutil.copytree(self.path, destination)
        print(f"Cloned repository to {destination}")

def main():
    """
    Example usage of the repository system.
    """
    # Create a new repository
    repo = Repository('my_project')
    
    # Stage files
    repo.add(['file1.txt', 'file2.py'])
    
    # Commit changes
    repo.commit("Initial commit")
    
    # Create a branch
    repo.branch('feature-branch')
    
    # Switch to the new branch
    repo.checkout('feature-branch')
    
    # Stage and commit on the new branch
    repo.add(['new_feature.txt'])
    repo.commit("Added new feature")
    
    # View commit history
    repo.log()
    
    # Compare branches
    repo.diff('main', 'feature-branch')
    
    # Clone the repository
    repo.clone('my_project_clone')

if __name__ == '__main__':
    main()