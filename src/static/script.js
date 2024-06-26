var return_to_top = document.getElementById("return-to-top");

var lidarr_get_artists_button = document.getElementById('lidarr-get-artists-button');
var start_stop_button = document.getElementById('start-stop-button');
var lidarr_status = document.getElementById('lidarr-status');
var lidarr_spinner = document.getElementById('lidarr-spinner');

var lidarr_item_list = document.getElementById("lidarr-item-list");
var lidarr_select_all_checkbox = document.getElementById("lidarr-select-all");
var lidarr_select_all_container = document.getElementById("lidarr-select-all-container");

var config_modal = document.getElementById('config-modal');
var lidarr_sidebar = document.getElementById('lidarr-sidebar');

var countries_list = document.querySelector(".countries-list");
var countries_checkboxes = document.querySelectorAll(".countries-list input");
var countries_selection = document.getElementById("countries-selection");
var save_message = document.getElementById("save-message");
var save_changes_button = document.getElementById("save-changes-button");
const lidarr_address = document.getElementById("lidarr-address");
const lidarr_api_key = document.getElementById("lidarr-api-key");

var countries_filter = [];
var lidarr_items = [];
var socket = io();

function check_if_all_selected() {
    var checkboxes = document.querySelectorAll('input[name="lidarr-item"]');
    var all_checked = true;
    for (var i = 0; i < checkboxes.length; i++) {
        if (!checkboxes[i].checked) {
            all_checked = false;
            break;
        }
    }
    lidarr_select_all_checkbox.checked = all_checked;
}

function previous_results() {
    try {
        return JSON.parse(localStorage.getItem('results')) || []
    } catch (e) {}
    return []
}

function previous_countries() {
    try {
        return JSON.parse(localStorage.getItem('countries')) || []
    } catch (e) {}
    return []
}

function load_lidarr_data(response) {
    var every_check_box = document.querySelectorAll('input[name="lidarr-item"]');
    if (response.Running) {
        start_stop_button.classList.remove('btn-success');
        start_stop_button.classList.add('btn-warning');
        start_stop_button.textContent = "Stop";
        every_check_box.forEach(item => {
            item.disabled = true;
        });
        lidarr_select_all_checkbox.disabled = true;
        lidarr_get_artists_button.disabled = true;
    } else {
        start_stop_button.classList.add('btn-success');
        start_stop_button.classList.remove('btn-warning');
        start_stop_button.textContent = "Start";
        every_check_box.forEach(item => {
            item.disabled = false;
        });
        lidarr_select_all_checkbox.disabled = false;
        lidarr_get_artists_button.disabled = false;
    }
    check_if_all_selected();
}

function append_gigs(gigs) {
    var gig_row = document.getElementById('gig-row');
    var template = document.getElementById('gig-template');

    gigs.forEach(function (gig) {
        var clone = document.importNode(template.content, true);
        var gig_col = clone.querySelector('#gig-column');
        
        if (gig.Location && countries_filter.length && !gig.Location.match(new RegExp(`(${countries_filter.join('|')})$`))) {
            console.debug(`skipping gig in ${gig.Location}`);
            return;
        }

        if (!gig.Status) {
            gig_col.querySelector('.status-indicator');
            gig_col.querySelector('.card-body').classList.add('status-green');

        } else if (gig.Status.match(/(Cancelled)/i)) {
            gig_col.querySelector('.card-body').classList.add('status-red');
            gig_col.querySelector('.status-indicator').setAttribute('title', gig.Status)

        } else {
            gig_col.querySelector('.status-indicator').setAttribute('title', gig.Status)
        }

        gig_col.querySelector('.card-title').textContent = gig.Name;
        gig_col.querySelector('.subtitle').textContent = `${gig.Location} (${gig.Venue})`;
        gig_col.querySelector('.date').textContent = gig.Evt_Date ? (new Date(gig.Evt_Date)).toLocaleDateString() : '';
        if (gig.Img_Link) {
            gig_col.querySelector('.card-img-top').src = gig.Img_Link;
            gig_col.querySelector('.card-img-top').alt = gig.Name;
        } else {
            gig_col.querySelector('.gig-img-container').removeChild(gig_col.querySelector('.card-img-top'));
        }
        gig_col.querySelector('.to-venue-btn').addEventListener('click', function () {
            window.open(gig.Evt_Link, '_blank');
        });
        gig_col.querySelector('.add-to-gagenda').addEventListener('click', function () {
            var date = (new Date(gig.Evt_Date)).toISOString().replace(/-|:|\.\d\d\d/g, '');
            var agenda_link = `https://calendar.google.com/calendar/r/eventedit?${new URLSearchParams({
                text: `${gig.Name} at ${gig.Venue}`,
                details: `${gig.Name} at ${gig.Venue}`,
                location: `${gig.Venue}, ${gig.Location}`,
                dates: `${date}/${date}`,
            }).toString()}`;
            window.open(agenda_link, '_blank');
        });
        gig_row.appendChild(clone);
    });
}

function add_to_lidarr(gig_name) {
    if (socket.connected) {
        socket.emit('adder', encodeURIComponent(gig_name));
    }
    else {
        show_toast("Connection Lost", "Please reload to continue.");
    }
}

function show_toast(header, message) {
    var toast_container = document.querySelector('.toast-container');
    var toast_template = document.getElementById('toast-template').cloneNode(true);
    toast_template.classList.remove('d-none');

    toast_template.querySelector('.toast-header strong').textContent = header;
    toast_template.querySelector('.toast-body').textContent = message;
    toast_template.querySelector('.text-muted').textContent = new Date().toLocaleString();

    toast_container.appendChild(toast_template);

    var toast = new bootstrap.Toast(toast_template);
    toast.show();

    toast_template.addEventListener('hidden.bs.toast', function () {
        toast_template.remove();
    });
}

function update_countries_handler(event) {
    var cb = event.target
    countries_filter = countries_filter
        .filter(c => c !== cb.value)
        .concat(cb.checked ? cb.value : []);

    countries_selection.textContent = countries_filter.length ? `${countries_filter.length} selected` : 'all'
    localStorage.setItem('countries', JSON.stringify(countries_filter))
}

countries_checkboxes.forEach(function(cb) {
    cb.addEventListener("change", update_countries_handler)
})

countries_selection.addEventListener("click", function() {
    countries_list.classList.toggle('d-none')
})

try {
    countries_filter = previous_countries();
    countries_selection.textContent = countries_filter.length ? `${countries_filter.length} selected` : 'all'
    countries_checkboxes.forEach(function(cb) {
        cb.checked = countries_filter.includes(cb.value)
    })
} catch (e) {}

return_to_top.addEventListener("click", function () {
    window.scrollTo({ top: 0, behavior: "smooth" });
});

lidarr_select_all_checkbox.addEventListener("change", function () {
    var is_checked = this.checked;
    var checkboxes = document.querySelectorAll('input[name="lidarr-item"]');
    checkboxes.forEach(function (checkbox) {
        checkbox.checked = is_checked;
    });
});

function load_artists() {
    lidarr_get_artists_button.disabled = true;
    lidarr_spinner.classList.remove('d-none');
    lidarr_status.textContent = "Accessing Lidarr API";
    lidarr_item_list.innerHTML = '';
    socket.emit("get_lidarr_artists");
}

lidarr_get_artists_button.addEventListener('click', load_artists);
load_artists();

start_stop_button.addEventListener('click', function () {
    var running_state = start_stop_button.textContent.trim() === "Start" ? true : false;
    if (running_state) {
        start_stop_button.classList.remove('btn-success');
        start_stop_button.classList.add('btn-warning');
        start_stop_button.textContent = "Stop";
        var checked_items = Array.from(document.querySelectorAll('input[name="lidarr-item"]:checked'))
            .map(item => item.value);
        document.querySelectorAll('input[name="lidarr-item"]').forEach(item => {
            item.disabled = true;
        });
        lidarr_get_artists_button.disabled = true;
        lidarr_select_all_checkbox.disabled = true;
        socket.emit("start_req", checked_items);
        if (checked_items.length > 0) {
            show_toast("Loading new gigs");
        }
    }
    else {
        start_stop_button.classList.add('btn-success');
        start_stop_button.classList.remove('btn-warning');
        start_stop_button.textContent = "Start";
        document.querySelectorAll('input[name="lidarr-item"]').forEach(item => {
            item.disabled = false;
        });
        lidarr_get_artists_button.disabled = false;
        lidarr_select_all_checkbox.disabled = false;
        socket.emit("stop_req");
    }
});

save_changes_button.addEventListener("click", () => {
    socket.emit("update_settings", {
        "lidarr_address": lidarr_address.value,
        "lidarr_api_key": lidarr_api_key.value,
    });
    save_message.style.display = "block";
    setTimeout(function () {
        save_message.style.display = "none";
    }, 1000);
});

config_modal.addEventListener('show.bs.modal', function (event) {
    socket.emit("load_settings");

    function handle_settings_loaded(settings) {
        lidarr_address.value = settings.lidarr_address;
        lidarr_api_key.value = settings.lidarr_api_key;
        socket.off("settingsLoaded", handle_settings_loaded);
    }
    socket.on("settingsLoaded", handle_settings_loaded);
});

lidarr_sidebar.addEventListener('show.bs.offcanvas', function (event) {
    socket.emit("side_bar_opened");
});

window.addEventListener('scroll', function () {
    if (window.innerHeight + window.scrollY >= document.body.offsetHeight) {
        socket.emit('load_more_gigs');
    }
});

window.addEventListener('touchmove', function () {
    if (window.innerHeight + window.scrollY >= document.body.offsetHeight) {
        socket.emit('load_more_gigs');
    }
});

window.addEventListener('touchend', () => {
    const { scrollHeight, scrollTop, clientHeight } = document.documentElement;
    if (Math.abs(scrollHeight - clientHeight - scrollTop) < 1) {
        socket.emit('load_more_gigs');
    }
});

socket.on("lidarr_sidebar_update", (response) => {
    if (response.Status == "Success") {
        lidarr_status.textContent = "Lidarr List Retrieved";
        lidarr_items = response.Data;
        lidarr_item_list.innerHTML = '';
        lidarr_select_all_container.classList.remove('d-none');

        for (var i = 0; i < lidarr_items.length; i++) {
            var item = lidarr_items[i];

            var div = document.createElement("div");
            div.className = "form-check";

            var input = document.createElement("input");
            input.type = "checkbox";
            input.className = "form-check-input";
            input.id = "lidarr-" + i;
            input.name = "lidarr-item";
            input.value = item.name;

            if (item.checked) {
                input.checked = true;
            }

            var label = document.createElement("label");
            label.className = "form-check-label";
            label.htmlFor = "lidarr-" + i;
            label.textContent = item.name;

            input.addEventListener("change", function () {
                check_if_all_selected();
            });

            div.appendChild(input);
            div.appendChild(label);

            lidarr_item_list.appendChild(div);
        }
    }
    else {
        lidarr_status.textContent = response.Code;
    }
    lidarr_get_artists_button.disabled = false;
    lidarr_spinner.classList.add('d-none');
    load_lidarr_data(response);
});

socket.on("refresh_gig", (gig) => {
    var gig_cards = document.querySelectorAll('#gig-column');
    gig_cards.forEach(function (card) {
        var card_body = card.querySelector('.card-body');
        var card_gig_name = card_body.querySelector('.card-title').textContent.trim();

        if (card_gig_name === gig.Name) {
            card_body.classList.remove('status-green', 'status-red', 'status-blue');

            var add_button = card_body.querySelector('.add-to-lidarr-btn');

            if (gig.Status === "Added" || gig.Status === "Already in Lidarr") {
                card_body.classList.add('status-green');
                add_button.classList.remove('btn-primary');
                add_button.classList.add('btn-secondary');
                add_button.disabled = true;
                add_button.textContent = gig.Status;
            } else if (gig.Status === "Failed to Add" || gig.Status === "Invalid Path") {
                card_body.classList.add('status-red');
                add_button.classList.remove('btn-primary');
                add_button.classList.add('btn-danger');
                add_button.disabled = true;
                add_button.textContent = gig.Status;
            } else {
                card_body.classList.add('status-blue');
                add_button.disabled = false;
            }
            return;
        }
    });
});

socket.on('more_gigs_loaded', function (data) {
    append_gigs(data);
    localStorage.setItem('results', JSON.stringify(previous_results().concat(data)))
});

function clear_results() {
    var gig_row = document.getElementById('gig-row');
    var gig_cards = gig_row.querySelectorAll('#gig-column');
    gig_cards.forEach(function (card) {
        card.remove();
    });
}

socket.on('clear', function () {
    clear_results()
    localStorage.setItem('results', null)
});

socket.on("new_toast_msg", function (data) {
    show_toast(data.title, data.message);
});

socket.on("disconnect", function () {
    show_toast("Connection Lost", "Please reconnect to continue.");
});

socket.on("connect", function () {
    clear_results()
    append_gigs(previous_results())
});

var preview_modal;
let preview_request_flag = false;

function preview_req(gig_name) {
    if (!preview_request_flag) {
        preview_request_flag = true;
        socket.emit("preview_req", encodeURIComponent(gig_name));
        setTimeout(() => {
            preview_request_flag = false;
        }, 1500);
    }
}

function show_audio_player_modal(gig, song) {
    preview_modal = new bootstrap.Modal(document.getElementById('audio-player-modal'));
    preview_modal.show();
    preview_modal._element.addEventListener('hidden.bs.modal', function () {
        stop_audio();
    });

    var modal_title_label = document.getElementById('audio-player-modal-label');
    if (modal_title_label) {
        modal_title_label.textContent = `${gig} - ${song}`;
    }
}

function play_audio(audio_url) {
    var audio_player = document.getElementById('audio-player');
    audio_player.src = audio_url;
    audio_player.play();
}

function stop_audio() {
    var audio_player = document.getElementById('audio-player');
    audio_player.pause();
    audio_player.currentTime = 0;
    audio_player.removeAttribute('src');
    preview_modal = null;
}

socket.on("spotify_preview", function (preview_info) {
    if (typeof preview_info === 'string') {
        show_toast("Error Retrieving Preview", preview_info);
    } else {
        var gig = preview_info.gig;
        var song = preview_info.song;
        show_audio_player_modal(gig, song);
        play_audio(preview_info.preview_url);
    }
});

socket.on("lastfm_preview", function (preview_info) {
    if (typeof preview_info === 'string') {
        show_toast("Error Retrieving Bio", preview_info);
    }
    else {
        var gig_name = preview_info.gig_name;
        var biography = preview_info.biography;
        var modal_title = document.getElementById('bio-modal-title');
        var modal_body = document.getElementById('modal-body');
        modal_title.textContent = gig_name;
        modal_body.textContent = biography;
        var modal = new bootstrap.Modal(document.getElementById('bio-modal-modal'));
        modal.show();
    }
});

const theme_switch = document.getElementById('theme-switch');
const saved_theme = localStorage.getItem('theme');
const saved_switch_position = localStorage.getItem('switch-position');

if (saved_switch_position) {
    theme_switch.checked = saved_switch_position === 'true';
}

if (saved_theme) {
    document.documentElement.setAttribute('data-bs-theme', saved_theme);
}

theme_switch.addEventListener('click', () => {
    if (document.documentElement.getAttribute('data-bs-theme') === 'dark') {
        document.documentElement.setAttribute('data-bs-theme', 'light');
    } else {
        document.documentElement.setAttribute('data-bs-theme', 'dark');
    }
    localStorage.setItem('theme', document.documentElement.getAttribute('data-bs-theme'));
    localStorage.setItem('switch_position', theme_switch.checked);
});
