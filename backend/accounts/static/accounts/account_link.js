'use strict';
// Link secrets stay in the fragment, which is not sent in HTTP requests.
const values = new URLSearchParams(window.location.hash.slice(1));
const token = values.get('token');
const purpose = values.get('purpose');
history.replaceState(null, '', window.location.pathname);
const paths = {verify: '/api/v1/auth/verification/confirm/', reset: '/api/v1/auth/password/reset/', change_email: '/api/v1/me/email/confirm/'};
const form = document.getElementById('confirmation');
const result = document.getElementById('result');
const password = document.getElementById('password');
if (purpose === 'reset') {
    document.getElementById('password-label').hidden = false;
    password.required = true;
}
if (!token || !Object.hasOwn(paths, purpose)) {
    form.hidden = true;
    result.textContent = 'الرابط غير صالح. / Invalid link.';
}
form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = form.querySelector('button');
    button.disabled = true;
    try {
        const body = {token};
        if (purpose === 'reset') body.password = password.value;
        const response = await fetch(paths[purpose], {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body), credentials: 'omit'});
        const data = await response.json();
        result.textContent = response.ok ? 'تم. يمكنك العودة إلى التطبيق. / Completed. Return to the app.' : JSON.stringify(data);
        if (response.ok) form.hidden = true;
    } catch {
        result.textContent = 'تعذر الاتصال. حاول مجدداً. / Unable to connect. Retry.';
    } finally {
        button.disabled = false;
    }
});
