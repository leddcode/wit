import distutils.dir_util
import filecmp
import os
from pathlib import Path
from random import choices
import shutil
import sys
from time import gmtime, strftime

import plotly.graph_objects as go

def init():
    current_dir = os.getcwd()
    path_wit = os.path.join(current_dir, '.wit')
    path_images = os.path.join(path_wit, 'images')
    path_staging_area = os.path.join(path_wit, 'staging_area')
    os.mkdir(path_wit)
    os.mkdir(path_images)
    os.mkdir(path_staging_area)
    update_activated_branch("master", path_wit)


def merge(branch_name):
    parent_dir = get_parent_directory()
    branch_commit_id = get_branch_id(parent_dir, branch_name)
    branch_path = os.path.join(parent_dir, f'.wit/images/{branch_commit_id}')
    prime_commit_id = get_prime_commit_id(parent_dir, branch_commit_id)
    prime_path = os.path.join(parent_dir, f'.wit/images/{prime_commit_id}')
    staging_area_path = os.path.join(parent_dir, '.wit/staging_area')
    files_to_merge = get_files_for_merging(branch_path, prime_path)
    for file in files_to_merge:
        distutils.file_util.copy_file(f"{branch_path}{file}", f"{staging_area_path}{file}")
    commit(f"Branch {branch_name} was merged")
    update_references(parent_dir, branch_commit_id)


def update_references(parent_dir, branch_commit_id):
    references_path = os.path.join(parent_dir, '.wit/references.txt')
    with open(references_path, 'r+', encoding='utf-8') as log:
        lines = log.readlines()
        lines[0] = lines[0].replace("\n", f",{branch_commit_id}\n")
        text = ''.join(lines)
        log.seek(0)
        log.write(text)


def get_files_for_merging(branch_path, prime_path):
    branch_files = get_files(branch_path)
    prime_files = [file[len(prime_path):] for file in get_files(prime_path)]
    result = []
    for path in branch_files:
        file = path[len(branch_path):]
        if file in prime_files and not filecmp.cmp(path, f"{prime_path}{file}"):
            result.append(file)
    return result


def get_prime_commit_id(parent_dir, branch_commit_id):
    head_history = get_ordered_list_of_commit_ids(parent_dir)
    while True:
        if branch_commit_id in head_history:
            return branch_commit_id
        branch_commit_id = get_parent_commit_id(branch_commit_id, parent_dir)


def update_activated_branch(branch_name, path_wit):
    with open(f"{path_wit}/activated.txt", "w", encoding="utf-8") as log:
        log.write(branch_name)


def get_activated_branch(parent_path):
    with open(f"{parent_path}/.wit/activated.txt", "r", encoding="utf-8") as f:
        return f.read()


def branch(branch_name):
    parent_dir = get_parent_directory()
    branches = get_branches(parent_dir)
    if branch_name not in branches:
        add_branch_label(parent_dir, branch_name)


def add_branch_label(parent_dir, name):
    head = get_head_commit_id(parent_dir)
    with open(f'{parent_dir}/.wit/references.txt', 'a', encoding='utf-8') as log:
        log.write(f'{name}={head}\n')


def checkout(commit_id):
    parent_dir = get_parent_directory()
    path_wit = os.path.join(parent_dir, '.wit')
    staging_area_path = os.path.join(parent_dir, '.wit/staging_area')
    branches = get_branches(parent_dir)
    if commit_id in branches:
        active_branch = commit_id
        commit_id = get_branch_id(parent_dir, active_branch)
        update_activated_branch(active_branch, path_wit)
    not_staged, untracked = check_status(staging_area_path)
    commit_path = os.path.join(parent_dir, f'.wit/images/{commit_id}')
    if not_staged:
        print(f"Process stopped - there're unstaged files:\n{not_staged}")
    elif os.path.isdir(commit_path):
        restore_tree(commit_path, parent_dir)
        log_references(parent_dir, commit_id, active_branch)
        for file in untracked:
            print(file, 'is untracked.')


def get_branch_id(parent_dir, branch_name):
    try:
        with open(f'{parent_dir}/.wit/references.txt', 'r', encoding='utf-8') as f:
            return f.read().split(f'\n{branch_name}=')[1].split("\n")[0]
    except IndexError as e:
        print(e, "=> references.txt is empty")
    except FileNotFoundError as e:
        print(e)


def restore_tree(commit_path, dest_path):
    try:
        distutils.dir_util.copy_tree(commit_path, dest_path)
    except distutils.errors.DistutilsFileError:
        print("Commit id doesn't exist")


def status():
    parent_dir = get_parent_directory()
    commit_id = get_parent_commit_id(parent_dir + '/references.txt')
    staging_area_path = os.path.join(parent_dir, '.wit/staging_area')
    staged = get_files(staging_area_path)
    not_staged, untracked = check_status(staging_area_path)
    reply = generate_reply(commit_id, staged, not_staged, untracked)
    print(reply)


def check_status(staging_area_path):
    not_staged = []
    untracked = []
    staging_area_list = os.listdir(staging_area_path)
    parent_dir = Path(staging_area_path).parent
    for file in staging_area_list:
        path = f'{staging_area_path}/{file}'
        path_log = os.path.join(parent_dir, f'~{os.listdir(staging_area_path)[0]}.txt')
        with open(path_log, 'r', encoding='utf-8') as f:
            source_path = f.read()
        common = [file.split(source_path)[-1][1:] for file in get_files(source_path)]
        _, mismatch, errors = filecmp.cmpfiles(path, source_path, common)
        not_staged.extend(mismatch)
        untracked.extend(errors)
    return not_staged, untracked


def generate_reply(commit_id, staged, not_staged, untracked):
    text = f'Last commit id: {commit_id}.\n\nChanges to be committed:\n{"-" * 50}\n'
    text += '\n'.join(staged)
    text += f'\n\nChanges not staged for commit:\n{"-" * 50}\n'
    text += '\n'.join(not_staged)
    text += f'\n\nUntracked files:\n{"-" * 50}\n'
    text += '\n'.join(untracked)
    return text


def commit(message):
    parent_dir = get_parent_directory()
    references_path = os.path.join(parent_dir, '.wit/references.txt')
    active_branch = get_activated_branch(parent_dir)
    if active_branch != "master" and not Path(references_path).is_file():
        print("First commit has to be made in master branch.")
    else:
        commit_id = ''.join(choices('1234567890abcdef', k=40))
        commit_folder_path = os.path.join(parent_dir, f'.wit/images/{commit_id}')
        commit_metadata_path = os.path.join(parent_dir, f'.wit/images/{commit_id}.txt')
        staging_area_path = os.path.join(parent_dir, '.wit/staging_area')
        shutil.copytree(staging_area_path, commit_folder_path)
        log_metadata(commit_metadata_path, message)
        log_references(parent_dir, commit_id, active_branch)


def log_metadata(path, message):
    with open(path, 'w+', encoding='utf-8') as log:
        parent_dir = str(Path(path).parent.parent.parent)
        parent = get_head_commit_id(parent_dir)
        date = strftime("%a %b %d %H:%M:%S %Y +0300", gmtime())
        log.write(f'parent={parent}\ndate={date}\nmessage={message}')


def log_references(parent_path, commit_id, active_branch):
    references_path = os.path.join(parent_path, '.wit/references.txt')
    if Path(references_path).is_file():
        text = gen_new_text(references_path, parent_path, commit_id, active_branch)
        with open(references_path, 'w', encoding='utf-8') as log:
            log.write(text)
    else:
        with open(references_path, 'w+', encoding='utf-8') as log:
            log.write(f'HEAD={commit_id}\nmaster={commit_id}\n')


def gen_new_text(references_path, parent_path, commit_id, active_branch):
    with open(references_path, 'r', encoding='utf-8') as log:
        lines = log.readlines()[1:]
        previous_head_commit_id = get_head_commit_id(parent_path)
        text = f'HEAD={commit_id}\n'
        for line in lines:
            branch_name, cid = line.split("=")
            if branch_name == active_branch and previous_head_commit_id == cid[:-1]:
                text += f'{active_branch}={commit_id}\n'
            else:
                text += line
        return text


def get_branches(parent_dir):
    with open(f'{parent_dir}/.wit/references.txt', 'r', encoding='utf-8') as f:
        lines = f.readlines()[1:]
        return [line.split("=")[0] for line in lines]


def get_head_commit_id(parent_dir):
    try:
        with open(f'{parent_dir}/.wit/references.txt', 'r', encoding='utf-8') as f:
            return f.readline().split('=')[1][:40]
    except IndexError as e:
        print(e, "=> references.txt is empty")
    except FileNotFoundError as e:
        print(e)


def get_parent_commit_id(commit_id, parent_dir):
    with open(f'{parent_dir}/.wit/images/{commit_id}.txt', 'r', encoding='utf-8') as f:
        return f.readline().split('=')[1][:40]


def add(path):
    if os.path.exists(os.path.abspath(path)):
        parent_dir = get_parent_directory()
        files = get_files(path)
        dir_to_add = path.split("/")[-1]
        staging_area_path = f'{parent_dir}' + r'\.wit\staging_area'
        for file in files:
            dest_path = staging_area_path + f'\\{dir_to_add}{file.split(dir_to_add)[-1]}'
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            shutil.copy(file, dest_path)
        with open(parent_dir + f'\\.wit\\~{dir_to_add}.txt', 'w+', encoding="utf-8") as f:
            f.write(os.path.abspath(path))
    else:
        print('Process stopped. Check the path.')


def get_parent_directory():
    cwd = os.path.abspath(os.getcwd())
    if os.path.isdir(f'{cwd}/.wit'):
        return cwd
    for parent in Path(cwd).parents:
        if os.path.isdir(f'{parent}/.wit'):
            return str(parent)
    raise FileNotFoundError("'.wit' folder doesn't exist in parent folders")


def get_files(path):
    path = os.path.abspath(path)
    if os.path.isfile(path):
        return [path]
    files = []
    for r, _, f in os.walk(path):
        for file in f:
            files.append(os.path.join(r, file))
    return files


def graph():
    parent_dir = get_parent_directory()
    li = get_ordered_list_of_commit_ids(parent_dir)
    fig = get_graph_fig(li)
    fig.show()


def get_ordered_list_of_commit_ids(parent_dir):
    head = get_head_commit_id(parent_dir)
    li = [head]
    while True:
        try:
            pci = get_parent_commit_id(li[-1], parent_dir)
            li.append(pci)
        except OSError as e:
            if li[-1] != 'None\n':
                print(e)
            break
    return li[:-1]


def get_graph_fig(list_of_commit_ids):
    x = list(range(len(list_of_commit_ids)))
    y = [0] * len(list_of_commit_ids)
    fig = go.Figure(data=[go.Scatter(
        x=x, y=y,
        mode='markers',
        marker_size=80)
    ])
    arrows = get_list_of_arrows(x, list_of_commit_ids)
    fig.update_layout(
        annotations=arrows,
        template="plotly_dark",
        xaxis_showgrid=False,
        yaxis_showgrid=False,
        xaxis_zeroline=False,
        yaxis_zeroline=False,
        xaxis_visible=False,
        yaxis_visible=False
    )
    return fig


def get_list_of_arrows(xaxis_list, list_of_commit_ids):
    head = go.layout.Annotation(dict(
        x=0,
        y=0,
        xref="x", yref="y",
        text='HEAD',
        xanchor='center',
        yanchor='top',
        showarrow=True,
        axref="x", ayref='y',
        ax=-0.5,
        ay=0.5,
        arrowhead=5,
        arrowwidth=2,
        arrowcolor='rgb(100,50,150)')
    )
    arrows = [head]
    for x in xaxis_list:
        if x == xaxis_list[-1]:
            label = go.layout.Annotation(dict(
                x=x,
                y=0,
                xref="x", yref="y",
                text=list_of_commit_ids[x][:6],
                xanchor='center',
                yanchor='top',
                showarrow=False)
            )
            arrows.append(label)
        else:
            arrow = go.layout.Annotation(dict(
                x=x + 1,
                y=0,
                xref="x", yref="y",
                text=list_of_commit_ids[x][:6],
                xanchor='center',
                yanchor='top',
                showarrow=True,
                axref="x", ayref='y',
                ax=x,
                ay=0,
                arrowhead=5,
                arrowwidth=2,
                arrowcolor='rgb(100,50,150)')
            )
            arrows.append(arrow)
    return arrows


if __name__ == '__main__':
    try:
        if sys.argv[1] == 'init':
            init()
        elif sys.argv[1] == 'add':
            add(sys.argv[2])
        elif sys.argv[1] == 'commit':
            message = ' '.join(sys.argv[2:])
            commit(message)
        elif sys.argv[1] == 'status':
            status()
        elif sys.argv[1] == 'checkout':
            checkout(sys.argv[2])
        elif sys.argv[1] == 'graph':
            graph()
        elif sys.argv[1] == 'branch':
            branch(sys.argv[2])
        elif sys.argv[1] == 'merge':
            merge(sys.argv[2])
    except (IndexError, FileExistsError) as e:
        print(e)