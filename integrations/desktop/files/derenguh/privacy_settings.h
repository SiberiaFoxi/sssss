// Privacy-mode hooks for DerenguhGram (tdesktop). SPDX: GPL-3.0-only
//
// These switches suppress YOUR OWN activity signals. They never touch other users'
// protected content. Wire the three `shouldSend*` gates into the exact MTProto call
// sites listed in docs/PRIVACY_MODES.md.
#pragma once

#include <QObject>
#include <QSettings>

namespace derenguh {

class PrivacySettings : public QObject {
    Q_OBJECT
public:
    static PrivacySettings &instance();

    // "Невидимка": do not publish presence / avoid online updates.
    [[nodiscard]] bool invisible() const { return _invisible; }
    void setInvisible(bool v);

    // "Нечиталка": do not send read receipts (messages.readHistory / read marks).
    [[nodiscard]] bool noReadReceipts() const { return _noRead; }
    void setNoReadReceipts(bool v);

    // "Неписалка": do not send messages.setTyping.
    [[nodiscard]] bool noTyping() const { return _noTyping; }
    void setNoTyping(bool v);

    // Gates used at the MTProto call sites.
    [[nodiscard]] bool shouldSendOnlineUpdate() const { return !_invisible; }
    [[nodiscard]] bool shouldSendReadReceipt() const { return !_noRead; }
    [[nodiscard]] bool shouldSendTyping() const { return !_noTyping; }

signals:
    void changed();

private:
    PrivacySettings();
    void load();
    void save();

    bool _invisible = false;
    bool _noRead = false;
    bool _noTyping = false;
    QSettings _store;
};

} // namespace derenguh
