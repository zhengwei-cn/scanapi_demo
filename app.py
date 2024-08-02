from flask import Flask, render_template, request, redirect, url_for, flash
import json
import os
import yaml
import subprocess
from collections import OrderedDict
from yaml.loader import SafeLoader



app = Flask(__name__)
app.secret_key = "supersecretkey"

CONFIG_FILE = "tasks.json"


def load_tasks():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {"tasks": []}


def save_tasks(tasks):
    with open(CONFIG_FILE, "w") as f:
        json.dump(tasks, f, indent=4)


def read_task_yaml(file_name):
    with open(file_name, "r") as f:
        return yaml.safe_load(f)


def save_task_yaml(file_name, file):
    with open(file_name, "w") as f:
        yaml.dump(file, f, default_flow_style=False, sort_keys=False, indent=2)


def ordered_load(file_path, Loader=SafeLoader, object_pairs_hook=OrderedDict):
    class OrderedLoader(Loader):
        pass
    def construct_mapping(loader, node):
        loader.flatten_mapping(node)
        return object_pairs_hook(loader.construct_pairs(node))
    OrderedLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        construct_mapping)
    with open(file_path, 'r') as stream:
        return yaml.load(stream, OrderedLoader)
    
def ordered_dump(data, stream=None, Dumper=yaml.SafeDumper, **kwds):
    class OrderedDumper(Dumper):
        pass
    def _dict_representer(dumper, data):
        return dumper.represent_dict(data.items())
    OrderedDumper.add_representer(OrderedDict, _dict_representer)
    return yaml.dump(data, stream, OrderedDumper, **kwds)

@app.route("/")
def index():
    tasks = load_tasks()
    return render_template("index.html", tasks=tasks["tasks"])


@app.route("/config", methods=["GET", "POST"])
def config():
    if request.method == "POST":
        task_name = request.form["task_name"]
        tasks = load_tasks()
        if task_name not in [task["name"] for task in tasks["tasks"]]:
            task = {"name": task_name}
            tasks["tasks"].append(task)
            save_tasks(tasks)

        endpoints = yaml.safe_load(request.form["endpoints"])
        file_name = task_name + ".yaml"
        save_task_yaml(file_name, endpoints)
        flash("Task saved successfully!")
        return redirect(url_for("index"))

    task_name = request.args.get("task_name")
    task = next(
        (task for task in load_tasks()["tasks"] if task["name"] == task_name), None
    )
    endpoints = ordered_dump(ordered_load(task_name + ".yaml")) if task else ""

    return render_template("config.html", task_name=task_name, endpoints=endpoints)


@app.route("/run_task/<task_name>")
def run_task(task_name):
    tasks = load_tasks()
    task = next((task for task in tasks["tasks"] if task["name"] == task_name), None)
    if task:
        try:
            report_file = generate_report_file(task_name)
            path = os.path.join("static", report_file)
            result = subprocess.run(
                ["scanapi", "run", task_name + ".yaml", "-o", path],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            flash(f"{task_name} Task Passed!")
            print(result.stdout.decode())
            return redirect(url_for("report", report_file=report_file))
        except subprocess.CalledProcessError as e:
            flash(f"{task_name} Task Failed! {e.stderr.decode()}")
            return redirect(url_for("report", report_file=report_file))
    else:
        flash("Task not found!")

    return redirect(url_for("index"))


@app.route("/delete_task/<task_name>")
def delete_task(task_name):
    tasks = load_tasks()
    task = next((task for task in tasks["tasks"] if task["name"] == task_name), None)
    if task:
        tasks["tasks"].remove(task)
        save_tasks(tasks)
        task_file = f"{task_name}.yaml"
        if os.path.exists(task_file):
            os.remove(task_file)
        report_file = generate_report_file(task_name)
        report_file = os.path.join("static", report_file)
        if os.path.exists(report_file):
            os.remove(report_file)
        flash("Task deleted successfully!")
    else:
        flash("Task not found!")

    return redirect(url_for("index"))


@app.route("/report")
def report():
    report_file = request.args.get("report_file")
    path = os.path.join("static", report_file)
    if os.path.exists(path):
        return render_template("report.html", report_file=report_file)
    else:
        flash("Report not found!")
        return redirect(url_for("index"))


def generate_report_file(task_name):
    return f"{task_name}-report.html"


if __name__ == "__main__":
    app.run(debug=True)
