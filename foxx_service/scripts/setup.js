'use strict';
const db = require('@arangodb').db;
const collections = ['User', 'AuditLog'];

collections.forEach((name) => {
    if (!db._collection(name)) {
        db._createDocumentCollection(name);
        console.log(`Created collection ${name}`);
    } else {
        console.log(`Collection ${name} already exists.`);
    }
});
