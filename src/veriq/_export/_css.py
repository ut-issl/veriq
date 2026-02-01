"""CSS styles for veriq HTML export."""

CSS = """
:root {
    --bg-color: #f8f9fa;
    --text-color: #212529;
    --border-color: #dee2e6;
    --primary-color: #0d6efd;
    --success-color: #198754;
    --warning-color: #ffc107;
    --danger-color: #dc3545;
    --info-color: #0dcaf0;
    --sidebar-width: 250px;
}

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    line-height: 1.6;
    color: var(--text-color);
    background-color: var(--bg-color);
}

header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 2rem;
    text-align: center;
}

header h1 {
    margin-bottom: 0.5rem;
}

header .subtitle {
    opacity: 0.9;
}

.container {
    display: flex;
    min-height: calc(100vh - 120px);
}

.sidebar {
    width: var(--sidebar-width);
    background: white;
    border-right: 1px solid var(--border-color);
    padding: 1.5rem;
    position: sticky;
    top: 0;
    height: fit-content;
    max-height: 100vh;
    overflow-y: auto;
}

.sidebar h2 {
    font-size: 1rem;
    text-transform: uppercase;
    color: #6c757d;
    margin-bottom: 1rem;
}

.sidebar ul {
    list-style: none;
}

.sidebar li {
    margin: 0.25rem 0;
}

.sidebar a {
    color: var(--text-color);
    text-decoration: none;
    display: block;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
}

.sidebar a:hover {
    background: var(--bg-color);
}

.sidebar ul ul {
    margin-left: 1rem;
}

.content {
    flex: 1;
    padding: 2rem;
    max-width: calc(100% - var(--sidebar-width));
}

section {
    margin-bottom: 2rem;
}

h2 {
    border-bottom: 2px solid var(--primary-color);
    padding-bottom: 0.5rem;
    margin-bottom: 1.5rem;
}

h3 {
    display: inline;
    font-size: 1.25rem;
}

h4 {
    color: #6c757d;
    margin-bottom: 0.75rem;
}

h5 {
    margin-bottom: 0.5rem;
}

details {
    background: white;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    margin-bottom: 1rem;
}

details summary {
    padding: 1rem;
    cursor: pointer;
    background: #f8f9fa;
    border-radius: 8px 8px 0 0;
}

details[open] summary {
    border-bottom: 1px solid var(--border-color);
}

.scope-content {
    padding: 1rem;
}

.section {
    margin-bottom: 1.5rem;
}

.calc-block {
    margin-bottom: 1rem;
    padding: 0.75rem;
    background: #f8f9fa;
    border-radius: 4px;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 0.5rem;
}

.data-table, .verification-table {
    background: white;
}

th, td {
    padding: 0.5rem;
    text-align: left;
    border-bottom: 1px solid var(--border-color);
}

th {
    background: #f1f3f4;
    font-weight: 600;
}

.inline-table {
    width: auto;
    margin: 0;
    font-size: 0.9em;
}

.inline-table.compact td {
    padding: 0.25rem 0.5rem;
}

.nested-row td {
    padding-left: 2rem;
}

.nested-key {
    color: #6c757d;
}

code {
    background: #e9ecef;
    padding: 0.125rem 0.375rem;
    border-radius: 3px;
    font-size: 0.9em;
}

.status {
    display: inline-block;
    padding: 0.125rem 0.5rem;
    border-radius: 4px;
    font-weight: 500;
}

.status.pass {
    background: #d1e7dd;
    color: #0f5132;
}

.status.fail {
    background: #f8d7da;
    color: #842029;
}

.status.satisfied {
    background: #cff4fc;
    color: #055160;
}

.status.not-verified {
    background: #fff3cd;
    color: #664d03;
}

.summary-panel {
    display: flex;
    gap: 1.5rem;
    padding: 1rem;
    background: white;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    margin-bottom: 1.5rem;
    flex-wrap: wrap;
}

.summary-panel span {
    font-weight: 500;
}

.requirements-tree {
    background: white;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1rem;
}

.req-tree {
    list-style: none;
}

.req-tree ul {
    list-style: none;
    margin-left: 1.5rem;
    border-left: 2px solid var(--border-color);
    padding-left: 1rem;
}

.req-node {
    margin: 0.5rem 0;
}

.req-node details {
    border: none;
    background: transparent;
}

.req-node summary {
    padding: 0.5rem;
    background: transparent;
    border-radius: 4px;
}

.req-node summary:hover {
    background: var(--bg-color);
}

.req-node.verified .status-icon { color: var(--success-color); }
.req-node.satisfied .status-icon { color: var(--info-color); }
.req-node.failed .status-icon { color: var(--danger-color); }
.req-node.not-verified .status-icon { color: var(--warning-color); }

.req-desc {
    color: #6c757d;
}

.req-verifications, .req-deps {
    margin-left: 1.5rem;
    padding: 0.25rem 0;
    color: #6c757d;
}

.req-verifications code {
    font-size: 0.85em;
}

.req-deps a {
    color: var(--primary-color);
}

.req-children {
    margin-top: 0.5rem;
}

@media (max-width: 768px) {
    .container {
        flex-direction: column;
    }

    .sidebar {
        width: 100%;
        position: relative;
        border-right: none;
        border-bottom: 1px solid var(--border-color);
    }

    .content {
        max-width: 100%;
    }
}
"""
