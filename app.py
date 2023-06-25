from flask import Flask, render_template, request
from repo import fetch_user_repositories,identify_most_complex_repository
import openai


app = Flask(__name__)



@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        github_url = request.form['github_url']
        repositories = fetch_user_repositories(github_url)
        most_complex_repository,justification = identify_most_complex_repository(repositories)
        if most_complex_repository is None:
            repo_link='none'
        else:
            repo_link = most_complex_repository['html_url']
         
        return render_template('result.html', link=repo_link,justification=justification)
    return render_template('index.html')

if __name__ == '__main__':
    app.run()