import requests
import openai
from requests.exceptions import ConnectTimeout, Timeout
import nbformat
from nbconvert.preprocessors import ExecutePreprocessor
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_user_repositories(github_url):
    # Extract the username from the GitHub URL
    username = github_url.split('/')[-1]

    # Make a GET request to the GitHub API to retrieve the user's repositories
    api_url = f"https://api.github.com/users/{username}/repos"
    response = requests.get(api_url)

    if response.status_code == 200:
        repositories = response.json()
        return repositories
    else:
        # Handle error case when the user or repositories are not found
        return []

def download_file(url, file_path):
    try:
        response = requests.get(url)
        response.raise_for_status()

        with open(file_path, 'wb') as file:
            file.write(response.content)

        return file_path
    except Exception as e:
        print(f"Error downloading file: {url}\n{str(e)}")
        return None

def preprocess_file(repository, item):
    code_snippet = None
    executed_notebook_path = None

    file_name = item['name']
    file_path = item['path']
    download_url = item['download_url']

    if file_name.endswith('.ipynb'):
        executed_notebook_path = download_file(download_url, file_path)

        if executed_notebook_path is not None:
            try:
                nb = nbformat.read(executed_notebook_path, as_version=4)
                code_cells = [cell for cell in nb['cells'] if cell['cell_type'] == 'code']
                code_snippet = '\n'.join([cell['source'] for cell in code_cells])
            except Exception as e:
                print(f"Error reading notebook file: {executed_notebook_path}\n{str(e)}")
                code_snippet = None
        else:
            print(f"Failed to download notebook file: {download_url}")

    return code_snippet, executed_notebook_path

def execute_notebook(notebook_path):
    nb = nbformat.read(notebook_path, as_version=4)
    ep = ExecutePreprocessor(timeout=6000, kernel_name='python3')  # Set the timeout limit as needed

    try:
        # Execute the notebook
        ep.preprocess(nb, {'metadata': {'path': '.'}})

        # Save the executed notebook
        executed_notebook_path = notebook_path.replace('.ipynb', '_executed.ipynb')
        nbformat.write(nb, executed_notebook_path)
        print(f"Executed notebook saved at {executed_notebook_path}")

        return executed_notebook_path

    except Exception as e:
        print(f"An error occurred during notebook execution: {str(e)}")
        raise e

def preprocess_code(repository):
    code_snippets = []

    if 'name' in repository:
        api_url = repository['contents_url'].split('{')[0]
        response = requests.get(api_url)

        if response.status_code == 200:
            repository_contents = response.json()

            with ThreadPoolExecutor() as executor:
                futures = []

                for item in repository_contents:
                    if item['type'] == 'file':
                        future = executor.submit(preprocess_file, repository, item)
                        futures.append(future)

                for future in as_completed(futures):
                    code_snippet, executed_notebook_path = future.result()
                    if code_snippet is not None:
                        code_snippets.append(code_snippet)

        else:
            print("Failed to fetch repository contents.")
    else:
        print("Failed to fetch repository name.")

    return code_snippets

def split_code(code):
    # Split the code into smaller chunks while respecting token limits
    # Example implementation using a simple approach
    
    # Split the code into lines
    lines = code.split('\n')
    
    # Initialize variables
    code_snippets = []
    current_snippet = ''
    token_count = 0
    
    for line in lines:
        # Calculate the number of tokens in the line
        tokens_in_line = len(line.split())
        
        # Check if adding the line would exceed the token limit
        if token_count + tokens_in_line > 1000:  # Example token limit, adjust as needed
            # Add the current snippet to the list
            code_snippets.append(current_snippet)
            
            # Reset the variables for the next snippet
            current_snippet = ''
            token_count = 0
        
        # Add the line to the current snippet
        current_snippet += line + '\n'
        token_count += tokens_in_line
    
    # Add the last snippet if it's not empty
    if current_snippet != '':
        code_snippets.append(current_snippet)
    
    return code_snippets

def generate_prompt(repository):
    prompt = ""
    prompt += f"Repository: {repository['name']}\n"
    prompt += f"Owner: {repository['owner']}\n"
    
    languages = repository.get('languages', [])
    prompt += f"Languages: {', '.join(languages)}\n"

    return prompt

def evaluate_complexity(prompt, code):
    # Set up your GPT or LangChain API credentials
    api_key = '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'
    model_name = 'curie'
    
    # Concatenate the prompt and code snippet
    instructions = f"""Given the following language and code, calculate its complexity score and provide a justification:

        Language:
        ```
        {prompt}
        ```
        Code:
        ```
        {code}
        ```
        
        Complexity Score:
        
        Justification:
        """

    # Make a request to the GPT or LangChain API
    response = openai.Completion.create(
        engine='davinci-codex',  # You can also try 'text-davinci-003' for less-costly option
        prompt=instructions,
        max_tokens=1000,
        n=1,
        stop=None,
        temperature=0.8,
        top_p=1.0,
        frequency_penalty=0.0,
        presence_penalty=0.0
    )
    
    # Retrieve the complexity score from the GPT or LangChain response
    completion = response.choices[0].text.strip().split('\n')
    complexity_score = completion[2].strip()
    justification = completion[4].strip()
    return complexity_score, justification





def identify_most_complex_repository(repositories):
    most_complex_repository = None
    fin_just='none'
    highest_complexity_score = -1
    
    with ThreadPoolExecutor() as executor:
        futures = []
        
        for repository in repositories:
            future = executor.submit(preprocess_code, repository)
            futures.append(future)
        
        for future, repository in zip(futures, repositories):
            code_snippets = future.result()
            
            prompt = generate_prompt(repository)
            repository_complexity = 0
            rep_just = ""  # Accumulate justification texts for each code snippet
            
            for code in code_snippets:
                complexity_score,just = evaluate_complexity(prompt, code)
                print(complexity_score,just)
                rep_just += just  # Accumulate the justification text
                repository_complexity += complexity_score
            
            if repository_complexity > highest_complexity_score:
                highest_complexity_score = repository_complexity
                most_complex_repository = repository
                fin_just = rep_just
    
    return most_complex_repository, fin_just
