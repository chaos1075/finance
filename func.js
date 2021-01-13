function setItem(x) {
    sessionStorage.setItem('symbol', x);
}
function getItem() {
    return sessionStorage.getItem('symbol');
}
function remItem() {
    sessionStorage.removeItem('symbol');
}