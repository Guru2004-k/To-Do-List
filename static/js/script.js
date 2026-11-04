// script.js – small helpers that make the pages nicer to use.

document.addEventListener("DOMContentLoaded", function () {
    // 1. Ask for confirmation before deleting a task.
    //    Any <form data-confirm="..."> shows that message first.
    document.querySelectorAll("form[data-confirm]").forEach(function (form) {
        form.addEventListener("submit", function (event) {
            if (!window.confirm(form.dataset.confirm)) {
                event.preventDefault(); // user clicked "Cancel"
            }
        });
    });

    // 2. Let the user close flash messages. Success messages hide by themselves.
    document.querySelectorAll(".flash").forEach(function (flash) {
        flash.querySelector(".flash-close").addEventListener("click", function () {
            flash.remove();
        });
        if (flash.classList.contains("flash-success")) {
            setTimeout(function () { flash.remove(); }, 4000);
        }
    });

    // 3. Show "123 / 500" under the description box while typing.
    document.querySelectorAll("[data-counter-for]").forEach(function (counter) {
        var textarea = document.getElementById(counter.dataset.counterFor);
        var max = counter.dataset.max;
        function update() {
            counter.textContent = textarea.value.length + " / " + max;
        }
        textarea.addEventListener("input", update);
        update();
    });

    // 4. Stop the form being sent with an empty title (friendly early check).
    var titleInput = document.getElementById("title");
    if (titleInput) {
        titleInput.form.addEventListener("submit", function (event) {
            if (titleInput.value.trim() === "") {
                event.preventDefault();
                titleInput.focus();
                titleInput.classList.add("input-error");
            }
        });
        titleInput.addEventListener("input", function () {
            titleInput.classList.remove("input-error");
        });
    }
});
