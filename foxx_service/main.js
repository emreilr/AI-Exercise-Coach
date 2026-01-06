'use strict';
const createRouter = require('@arangodb/foxx/router');
const router = createRouter();
const joi = require('joi');
const db = require('@arangodb').db;
const errors = require('@arangodb').errors;
const aql = require('@arangodb').aql;

module.context.use(router);

// --- TRIGGER LOGIC (Helper Function) ---
// In a real Foxx app, this could also be attached to collection events, 
// but calling it explicitly ensures the "Trigger" behavior within this Transactional Procedure.
function triggerAuditLog(action, details, user) {
    const auditCollection = db._collection('AuditLog');
    auditCollection.save({
        action: action,
        details: details,
        performed_by: user,
        timestamp: new Date().toISOString()
    });
}

// --- STORED PROCEDURE (Endpoint) ---
router.post('/developers', function (req, res) {
    const data = req.body;
    const users = db._collection('User');

    // Transaction Block: Ensure Atomicity
    // Transaction Block: Ensure Atomicity
    const result = db._executeTransaction({
        collections: {
            write: ['User', 'AuditLog']
        },
        action: function () {

            // 1. Business Logic Check (Before Insert)
            const existing = db._query(aql`
        FOR u IN User
        FILTER u.username == ${data.username}
        RETURN u
      `).toArray();

            if (existing.length > 0) {
                return { error: true, status: 409, message: 'Username is already taken.' };
            }

            // 2. Insert User
            const meta = users.save({
                username: data.username,
                hashed_password: data.hashed_password,
                full_name: data.full_name,
                user_type: 'developer',
                created_at: new Date().toISOString(),
                is_verified: true
            });

            // 3. Fire Trigger (Audit Log)
            triggerAuditLog('CREATE_DEVELOPER', `Created developer: ${data.username}`, 'system_admin');

            return { success: true, meta: meta };
        }
    });

    if (result.error) {
        res.status(result.status);
        res.send({ errorMessage: result.message });
        return;
    }

    res.send({ success: true, message: 'Developer created via Foxx Procedure', username: data.username });

})
    .body(joi.object({
        username: joi.string().required(),
        hashed_password: joi.string().required(),
        full_name: joi.string().allow('').optional()
    }).required(), 'User Data')
    .response(200, ['application/json'])
    .summary('Create a Developer (Stored Proc)')
    .description('Creates a user and triggers an audit log entry transactionally.');
