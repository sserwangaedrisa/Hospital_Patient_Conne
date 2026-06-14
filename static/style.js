document.addEventListener('DOMContentLoaded', () => {

    const chatspace = document.querySelector('#chatspace');
    const sendButton = document.querySelector('#sendButton');
    const messageInput = document.querySelector('#messageInput');
    const chatForm = document.querySelector('#form'); // chat.html form
    const medForm = document.querySelector('#forms'); // medication.html form
    const respond = document.querySelector('#respond');
    const medicationRows = document.querySelectorAll('.med-id');
    const nextMedTime = document.querySelectorAll('.time');
    const remainingDosage = document.querySelectorAll('.remaining');
    const medStatus = document.querySelectorAll('.dosageStatus')
    const chatbot_form = document.querySelector('#chatbot_form')

    let socket;
    try {
        socket = io();
        socket.on('connect', () => {
            console.log('Connected to socket.io server');
        });
    } catch (err) {
        console.warn('Socket.io not available on this page');
    }

    // 🔹 CHAT PAGE LOGIC
    if (chatForm && chatspace && messageInput) {
        console.log('Chat page detected');

        const displayMessage = (message, origin, time) => {
            const newMessageDiv = document.createElement('div');
            newMessageDiv.innerHTML = message;
            const timeElement = document.createElement('p');
            timeElement.className = 'time';

            if (origin === 'myOwn') {
                const now = new Date();
                timeElement.textContent = now.toISOString().slice(0, 16).replace('T', ' ');
                newMessageDiv.className = 'message-right';
            } else if (origin === 'server') {
                timeElement.textContent = time;
                newMessageDiv.className = 'message-left';
            }

            newMessageDiv.appendChild(timeElement);
            chatspace.appendChild(newMessageDiv);
        };

        chatForm.addEventListener('submit', (event) => {
            event.preventDefault();
            const message = messageInput.value.trim();
            if (!message) return;

            displayMessage(message, 'myOwn');
            messageInput.value = '';

            if (socket) socket.emit('sendMessage', message, socket.id);
        });

        if (socket) {
            socket.on('serverMessage', (data) => {
                displayMessage(data.message, data.origin, data.time);
            });
        }
    }


    // 🔹 MEDICATION PAGE LOGIC

    if (medForm && respond) {


        medStatus.forEach(element => {
            if (element.textContent === 'completed') {
                element.classList.add('text-success', 'fw-bold')
            } else {
                element.classList.add('text-warning' ,'fw-bold')
            }
        })

        medForm.addEventListener('submit', async (event) => {
            event.preventDefault();

            try {
                const response = await fetch('/response', {
                    method: 'POST',
                    body: new FormData(medForm),
                });

                console.log(new FormData)
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const result = await response.json();

                if (!result.medication) {
                    console.error('Unexpected response:', result);
                    return;
                }

                const med = result.medication;
                // ✅ Update medication row
                const medName = med.name;
                const tableRows = document.querySelectorAll('.medTable tbody tr');

                let updated = false;
                tableRows.forEach(row => {
                    const nameCell = row.cells[0]; // first <td> = medication name
                    if (nameCell.textContent.trim() === medName) {
                        row.querySelector('.time').textContent = med.next_dosage_time;
                        row.querySelector('.remaining').textContent = med.dosage_remaining;
                        row.querySelector('.dosageStatus').textContent = med.status;



                        const statusCell = row.cells[7]; // last <td> in the row (Status)
                        if (parseInt(med.dosage_remaining) <= 0) {
                        statusCell.classList.add('text-success', 'fw-bold');
                        statusCell.classList.remove('text-warning');
                    } else {
                        statusCell.textContent = 'In Progress';
                        statusCell.classList.add('text-warning', 'fw-semibold');
                        statusCell.classList.remove('text-success');
                    }

                    updated = true;
                    console.log(` Updated medication: ${medName}`);

                        updated = true;
                        console.log(`Updated medication: ${medName}`);
                    }
                });

                if (!updated) {
                    console.warn(` No matching row found for medication: ${medName}`);
                }

            } catch (err) {
                console.error(' Error updating medication:', err);
            }


        });



    }

    // 🔹CHATBOT LOGIC

     if (chatbot_form) {
            chatbot_form.addEventListener('submit', async (event) => {
                event.preventDefault()
                const main_div = document.querySelector('#main_div');
                const input = document.querySelector('#chatbot_input');
                const query = input.value.trim();
                if (!query) return;
                input.value = "";
                const userMessage = document.createElement('div');
                userMessage.innerHTML = query;
                userMessage.className = 'message-right fs-5 mt-3 p-2 w-fit ';
                main_div.appendChild(userMessage);


                try {
                    const ai_response = await fetch('/chatbot_api', {
                    method: 'POST',
                    body: JSON.stringify({ message: query }),
                    headers: {
                        'Content-Type': 'application/json'
                        }
                    })


                    if (!ai_response.ok) throw new Error(`HTTP ${ai_response.status}`);
                    const responseData = await ai_response.json()


                    const aiMessage = responseData.response;
                    const newMessage = document.createElement('div');
                    newMessage.innerHTML = aiMessage;
                    newMessage.className = 'message-left fs-5 mt-3 p-2';
                    main_div.appendChild(newMessage);


                } catch (err) {
                    console.error('Error fetching ai response: ', err)
                }

            })
        }

});
