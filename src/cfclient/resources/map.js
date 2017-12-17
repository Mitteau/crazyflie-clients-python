var map = L.map('map', {
    center: [51.505, -0.09],
    zoom: 13
});
L.tileLayer('http://www.openstreetmap.org/#map=1/14/14').addTo(map);



/*
var map = L.map('map').setView([55.607526, 13.018219], 16);
//L.tileLayer('http://otile{s}.mqcdn.com/tiles/1.0.0/map/{z}/{x}/{y}.png', {
L.tileLayer('http://www.openstreetmap.org/#map={z}/{x}/{y}', {
    maxZoom: 18,
    attribution: 'Map data &copy; <a href="http://openstreetmap.org">OpenStreetMap</a> contributors, ' +
        'tiles Courtesy of <a href="http://www.mapquest.com/" target="_blank">MapQuest</a>',
    subdomains: '1',//'1234',
}).addTo(map);

var cf = L.circle([55.607526, 13.018219], 1, {
    color: 'blue',
    fillColor: 'blue',
    fillOpacity: 1
}).addTo(map);

var accuracy = L.circle([55.607526, 13.018219], 0, {
    color: 'red',
    fillColor: '#f03',
    fillOpacity: 0.5
}).addTo(map);

if(typeof MainWindow != 'undefined') {
    var onMapMove = function() { MainWindow.onMapMove(map.getCenter().lat, map.getCenter().lng) };
    map.on('move', onMapMove);
    onMapMove();
}




var map = L.map('map').setView([55.607526, 13.018219], 16);
L.tileLayer('http://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png?', {
//L.tileLayer('http://www.openstreetmap.org/#map={z}/{x}/{y}', {
    maxZoom: 18,
    attribution: 'Map data &copy; <a href="http://openstreetmap.org">OpenStreetMap</a> contributors, ' +
        'tiles Courtesy of <a href="http://www.mapquest.com/" target="_blank">MapQuest</a>',
    subdomains: '1'//'1234',
}).addTo(map);


//var map = L.map('map', {
//    center: [51.505, -0.09],
 //   zoom: 13
//}).addTo(map);
//L.tileLayer('http://www.openstreetmap.org/#map={z}/{x}/{y}?{foo}.png', {foo: 'bar'}).addTo(map);
//var map = L.map('map').setView([55.607526, 13.018219], 16);
//L.tileLayer('http://otile{s}.mqcdn.com/tiles/1.0.0/map/{z}/{x}/{y}.png






var cf = L.circle([55.607526, 13.018219], 1, {
    color: 'blue',
    fillColor: 'blue',
    fillOpacity: 1
}).addTo(map);

var accuracy = L.circle([55.607526, 13.018219], 0, {
    color: 'red',
    fillColor: '#f03',
    fillOpacity: 0.5
}).addTo(map);

if(typeof MainWindow != 'undefined') {
    var onMapMove = function() { MainWindow.onMapMove(map.getCenter().lat, map.getCenter().lng) };
    map.on('move', onMapMove);
    onMapMove();
}*/
