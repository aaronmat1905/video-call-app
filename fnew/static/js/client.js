// WebRTC configuration
const configuration = {
    iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
        { urls: 'stun:stun1.l.google.com:19302' }
    ]
};

// Global variables
let localStream = null;
let peerConnection = null;
let currentCall = null;
let socket = null;
let username = null;

// DOM elements
const videoGrid = document.getElementById('video-grid');
const localVideo = document.getElementById('localVideo');
const remoteVideo = document.getElementById('remoteVideo');
const userList = document.getElementById('userList');
const usernameInput = document.getElementById('usernameInput');
const registerBtn = document.getElementById('registerBtn');
const callNotification = document.getElementById('callNotification');
const callerInfo = document.getElementById('callerInfo');
const acceptCallBtn = document.getElementById('acceptCall');
const rejectCallBtn = document.getElementById('rejectCall');
const endCallBtn = document.getElementById('endCall');

// Initialize socket connection
function initializeSocket() {
    socket = io({
        secure: true,
        rejectUnauthorized: false,
        transports: ['websocket']
    });

    // Socket event handlers
    socket.on('connect', () => {
        console.log('Connected to server');
        showToast('Connected to server', 'success');
    });

    socket.on('disconnect', () => {
        console.log('Disconnected from server');
        showToast('Disconnected from server', 'error');
    });

    socket.on('user_list', (users) => {
        console.log('Received user list:', users);
        updateUserList(users);
    });

    socket.on('incoming_call', async (data) => {
        handleIncomingCall(data);
    });

    socket.on('call_answered', async (data) => {
        handleCallAnswered(data);
    });

    socket.on('call_rejected', (data) => {
        handleCallRejected(data);
    });

    socket.on('call_ended', () => {
        handleCallEnded();
    });

    socket.on('ice_candidate', (data) => {
        handleIceCandidate(data);
    });
}

// User registration
registerBtn.addEventListener('click', async () => {
    username = usernameInput.value.trim();
    if (username) {
        try {
            // Get user media
            localStream = await navigator.mediaDevices.getUserMedia({
                video: true,
                audio: true
            });
            localVideo.srcObject = localStream;

            // Register with server
            socket.emit('register', { username });
            
            // Update UI
            document.getElementById('registration').style.display = 'none';
            document.getElementById('main-content').style.display = 'flex';
            showToast(`Registered as ${username}`, 'success');
        } catch (err) {
            console.error('Error accessing media devices:', err);
            showToast('Could not access camera/microphone', 'error');
        }
    }
});

// Update user list
function updateUserList(users) {
    if (!userList) return;
    userList.innerHTML = '';
    users.forEach(user => {
        if (user !== username) {
            const li = document.createElement('li');
            li.className = 'user-item';
            
            const userInfo = document.createElement('div');
            userInfo.className = 'user-info';
            
            const userStatus = document.createElement('div');
            userStatus.className = 'user-status';
            
            const userName = document.createElement('span');
            userName.className = 'user-name';
            userName.textContent = user;
            
            const callButton = document.createElement('button');
            callButton.className = 'call-button';
            callButton.innerHTML = '<i class="fas fa-video"></i>';
            callButton.onclick = () => initiateCall(user);
            
            userInfo.appendChild(userStatus);
            userInfo.appendChild(userName);
            li.appendChild(userInfo);
            li.appendChild(callButton);
            userList.appendChild(li);
        }
    });
}

// Media stream handling
async function setupLocalStream() {
    try {
        localStream = await navigator.mediaDevices.getUserMedia({
            video: true,
            audio: true
        });
        localVideo.srcObject = localStream;
        showToast('Camera and microphone accessed', 'success');
    } catch (error) {
        console.error('Error accessing media devices:', error);
        showToast('Failed to access camera/microphone', 'error');
    }
}

// Call handling
async function initiateCall(targetUser) {
    if (currentCall) {
        showToast('You are already in a call', 'warning');
        return;
    }

    try {
        currentCall = targetUser;
        createPeerConnection();

        // Add local stream
        localStream.getTracks().forEach(track => {
            peerConnection.addTrack(track, localStream);
        });

        // Create and send offer
        const offer = await peerConnection.createOffer();
        await peerConnection.setLocalDescription(offer);

        socket.emit('call_user', {
            target: targetUser,
            offer: offer
        });

        showToast(`Calling ${targetUser}...`, 'info');
    } catch (error) {
        console.error('Error initiating call:', error);
        handleCallError(error);
    }
}

function handleIncomingCall(data) {
    if (currentCall) {
        socket.emit('call_rejected', { target: data.caller });
        return;
    }

    callerInfo.textContent = `Incoming call from ${data.caller}`;
    callNotification.style.display = 'flex';
    
    // Play notification sound
    playNotificationSound();

    acceptCallBtn.onclick = async () => {
        try {
            currentCall = data.caller;
            createPeerConnection();

            // Add local stream
            localStream.getTracks().forEach(track => {
                peerConnection.addTrack(track, localStream);
            });

            // Set remote description and create answer
            await peerConnection.setRemoteDescription(new RTCSessionDescription(data.offer));
            const answer = await peerConnection.createAnswer();
            await peerConnection.setLocalDescription(answer);

            socket.emit('make_answer', {
                target: data.caller,
                answer: answer
            });

            callNotification.style.display = 'none';
            endCallBtn.style.display = 'block';
        } catch (error) {
            console.error('Error accepting call:', error);
            handleCallError(error);
        }
    };

    rejectCallBtn.onclick = () => {
        socket.emit('call_rejected', { target: data.caller });
        callNotification.style.display = 'none';
    };
}

async function handleCallAnswered(data) {
    try {
        await peerConnection.setRemoteDescription(new RTCSessionDescription(data.answer));
        endCallBtn.style.display = 'block';
    } catch (error) {
        console.error('Error handling call answer:', error);
        handleCallError(error);
    }
}

function handleCallRejected(data) {
    showToast(data.message || 'Call was rejected', 'warning');
    cleanupCall();
}

function handleCallEnded() {
    showToast('Call ended', 'info');
    cleanupCall();
}

function handleIceCandidate(data) {
    if (peerConnection && data.candidate) {
        peerConnection.addIceCandidate(new RTCIceCandidate(data.candidate))
            .catch(error => console.error('Error adding ICE candidate:', error));
    }
}

// WebRTC setup
function createPeerConnection() {
    peerConnection = new RTCPeerConnection(configuration);

    peerConnection.ontrack = (event) => {
        remoteVideo.srcObject = event.streams[0];
    };

    peerConnection.onicecandidate = (event) => {
        if (event.candidate) {
            socket.emit('ice_candidate', {
                target: currentCall,
                candidate: event.candidate
            });
        }
    };

    peerConnection.oniceconnectionstatechange = () => {
        if (peerConnection.iceConnectionState === 'disconnected') {
            handleCallEnded();
        }
    };
}

// Cleanup functions
function cleanupCall() {
    if (peerConnection) {
        peerConnection.close();
        peerConnection = null;
    }
    
    if (remoteVideo.srcObject) {
        remoteVideo.srcObject.getTracks().forEach(track => track.stop());
        remoteVideo.srcObject = null;
    }

    currentCall = null;
    endCallBtn.style.display = 'none';
    callNotification.style.display = 'none';
}

// Utility functions
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.add('show');
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }, 100);
}

function playNotificationSound() {
    const audio = new Audio('/static/sounds/notification.mp3');
    audio.play().catch(error => console.log('Error playing notification sound:', error));
}

// Event listeners
endCallBtn.addEventListener('click', () => {
    if (currentCall) {
        socket.emit('end_call', { target: currentCall });
        cleanupCall();
    }
});

// Initialize when the document is loaded
document.addEventListener('DOMContentLoaded', () => {
    initializeSocket();
}); 