// The index of the currently open info, used to go to previous and next info
let info_index = 0;

// The currently open information
let current_info = null;

// The source that is currently open (kind and subtype)
let opened_source = null;

// If non-zero ignore the coming n selection changes
let ignore_selection = 0;

// Set the (text) content of the inspect box and it's title
function set_inspect(title, text, table=false) {
  ignore_selection += 1;

  // Make the first letter of title uppercase
  document.getElementById('inspect-title').textContent =
    title.charAt(0).toUpperCase() + title.slice(1);

  let content = document.getElementById('inspect-text-content');
  content.textContent = text;

  content.style = '';
  document.getElementById('inspect-figure-content').style = 'display: none';

  if (table) {
    content.className = 'inspect-table';
  } else {
    content.className = '';
  }
}

// Display a section in the inspect panel
function load_section(article, index) {
  opened_source = {'kind': 'section', 'subtype': index};
  fetch(`/${article}/sections/${index}`)
    .then(res => res.json())
    .then(out => set_inspect(`${out['name']}`, out['content']))
    .catch(err => { throw err });
};

// Display a figure in the inspect panel
function load_figure(article, index, caption) {
  fetch(`/${article}/figures/${index}`)
    .then(res => res.json())
    .then(out => {
      if (caption) {
        opened_source = {'kind': 'figure caption', 'subtype': index};
        set_inspect(`${out['title']} caption`, out['caption'])
      } else {
        opened_source = {'kind': 'figure', 'subtype': index};
        let figure_link = document.getElementById('inspect-figure-content')
        figure_link.href = `/${article}/img/${index}`
        figure_link.firstElementChild.src = `/${article}/img/${index}`

        figure_link.style = '';
        document.getElementById('inspect-text-content').style = 'display: none';

        // Also change WPD image
        fetch(`/${article}/wpd/${index}`)
          .catch(err => { throw err });
      }
    })
    .catch(err => { throw err });
};

// Display a table in the inspect panel
function load_table(article, index, caption) {
  fetch(`/${article}/tables/${index}`)
    .then(res => res.json())
    .then(out => {
      if (caption) {
        opened_source = {'kind': 'table caption', 'subtype': index};
        set_inspect(`${out['title']} caption`, out['caption'])
      } else {
        opened_source = {'kind': 'table', 'subtype': index};
        set_inspect(`${out['title']}`, out['content'], table=true)
      }
    })
    .catch(err => { throw err });
};

// Display metadata in the inspect panel
function load_metadata(article, data) {
  opened_source = {'kind': 'metadata', 'subtype': data};
  fetch(`/${article}/metadata/${data}`)
    .then(res => res.text())
    .then(out => set_inspect(`${data}`, out))
    .catch(err => { throw err });
};

// Highlight and display the particular source from the article
function view_source(article, source) {
  // Show the source
  let text = true;
  switch (source['kind']) {
    case 'section':
      load_section(article, source['subtype']);
      break;
    case 'metadata':
      load_metadata(article, source['subtype']);
      break;
    case 'figure':
      text = false;
      load_figure(article, source['subtype'], false);
      break;
    case 'figure caption':
      load_figure(article, source['subtype'], true);
      break;
    case 'table':
      load_table(article, source['subtype'], false);
      break;
    case 'table caption':
      load_table(article, source['subtype'], true);
      break;
    default:
      console.log(`No such source kind ${source[kind]}`);
      return;
  }

  // Highlight the interesting part of source (but wait for the DOM to first update)
  if (text) {
    ignore_selection += 2;

    let update_selection = function() {
      let content = document.getElementById('inspect-text-content');

      // Try to update the selection until DOM is updated
      let range = document.createRange();
      try {
        range.setStart(content.firstChild, source['location']['start']);
        range.setEnd(content.firstChild, source['location']['end']);
      } catch (error) {
        setTimeout(update_selection, 100);
        return;
      }

      let sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
    };

    setTimeout(update_selection, 100);
  }

}

// Given a info object and associated article, make it active
function load_info(article, info, view_src) {
  document.getElementById('information-title').textContent = `Identified information`;
  document.getElementById('information-description').textContent = info['description']['info'];
  document.getElementById('information-content').textContent = info['data'];
  document.getElementById('information-content').placeholder = info['description']['data'];

  if (view_src) {
    // Load the information source
    view_source(article, info['source']);
  }

  // Store the current information
  current_info = info;
}

// Returns a promise of the number of info pieces for the article
function get_info_count(article, url) {
  return fetch(`/${article}/${url}`)
    .then(res => res.json())
    .then(out => out['length'])
    .catch(err => { throw err });
}

// Loads the (bound checked) info (by index) from the article
function load_identify_info(article, index) {
  get_info_count(article, 'identified').then(count => {
    // Bound check the input
    if (index < 0) {
      index = 0;
    } else if (count <= index) {
      index = count - 1;
    }

    // Update the global index
    info_index = index;

    // Load the info
    fetch(`/${article}/identified/${info_index}`)
      .then(res => res.json())
      .then(out => load_info(article, out, true))
      .catch(err => { throw err });
  });
}

// Deletes the given info uuid from article
function delete_info(article, uuid) {
  // Remove the info from server
  fetch(`/${article}/delete/${uuid}`, {
    method: 'POST'
  });

  // Remove the info card from summary if existent (make sure to remove multiple
  // if something has gone wrong and multiple cards share id's - important to
  // always match server behavior)
  let uuid_elements = document.getElementsByClassName(uuid);
  while(uuid_elements.length != 0) {
    uuid_elements[0].remove();
  }
}

// Stores the current information to the given article
function store_info(article) {
  // Update the info with the latest
  let info = current_info;
  info['stamp'] = new Date().toISOString();
  info['data'] = document.getElementById("information-content").textContent;
  info['uuid'] = crypto.randomUUID();

  // Store the info on the server
  fetch(`/${article}/store`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(info)
  });

  // Add the new information to the summary panel
  add_info_card(article, info);
}

// Adds the given info as a new card in the summary panel
function add_info_card(article, info) {
  let list = document.getElementById('summary-list');

  // The expanding is checked if true
  let expanding = '';
  if (info['expanding']) {
    expanding = 'checked';
  }

  let card = document.createElement('li');
  card.className = info['uuid'];
  card.innerHTML = `
    <form action="/${article}/update/${info['uuid']}" method="POST" target="form-target">
      <button onclick='delete_info(${article}, "${info['uuid']}")'>Delete</button>
      <button onclick='view_source(${article}, ${JSON.stringify(info['source'])}, true)'>View source</button>
      <input type="submit" value="Apply">
      <hr>
      <table>
        <tr>
          <td><label>Title</label></td>
          <td><input name="title" value="${info['title']}"></td>
        </tr><tr>
          <td><label>Content</label></td>
          <td><input name="data" value="${info['data']}"></td>
        </tr><tr>
          <td><label>Sample association</label></td>
          <td><input name="sample" type="number" value="${info['sample']}"></td>
        </tr><tr>
          <td><label>Timestamp</label></td>
          <td><input name="stamp" value="${info['stamp']}"></td>
        </tr><tr>
          <td><label>Expanding</label></td>
          <td><input name="expanding" type="checkbox" ${expanding}></td>
        </tr>
      </table>
    </form>
    `;

  // Add card to panel
  document.getElementById('summary-list').append(card);
}

// Load / update the summary pane containing all info associated with the article
function load_info_summary(article) {
  // Clear the summary list
  let list = document.getElementById('summary-list');
  list.textContent = '';

  get_info_count(article, 'info').then(count => {
    for (let i = 0; i < count; i++) {
      // Load the informations
      fetch(`/${article}/info/${i}`)
        .then(res => res.json())
        .then(info => add_info_card(article, info))
        .catch(err => { throw err });
    }
  });
}

// Is called when a selection is detected in the inspect text area. This updates
// the source of the current information
function inspect_select() {
  // Honor explicitly ignored selections
  if (0 < ignore_selection) {
    ignore_selection -= 1;
    return;
  }

  const text = document.getElementById('inspect-text-content');

  // Get the selected text
  const range = document.getSelection().getRangeAt(text);
  const selected = range.toString();

  // If the event does not exclusively regard the inspect text
  if (!range.startContainer.parentNode.isSameNode(text) ||
    !range.endContainer.parentNode.isSameNode(text)) {
    return;
  }

  // Ignore empty selection
  if (selected == "") {
    return;
  }

  // Update the source and data
  current_info['data'] = selected;
  current_info['source'] = {
    'article': current_info['source']['article'],
    'kind': opened_source['kind'],
    'subtype': opened_source['subtype'],
    'location': {
      'start': range.startOffset,
      'end': range.endOffset,
    }
  };

  // Update the current info
  load_info(current_info['source']['article'], current_info, false);
}

// Add the select listener
document.addEventListener('selectionchange', inspect_select)
