// SPDX-License-Identifier: GPL-3.0-only
#include "privacy_settings.h"

namespace derenguh {

PrivacySettings &PrivacySettings::instance() {
    static PrivacySettings s;
    return s;
}

PrivacySettings::PrivacySettings()
    : _store(QSettings::IniFormat, QSettings::UserScope,
             QStringLiteral("DerenguhGram"), QStringLiteral("privacy")) {
    load();
}

void PrivacySettings::load() {
    _invisible = _store.value(QStringLiteral("invisible"), false).toBool();
    _noRead = _store.value(QStringLiteral("noReadReceipts"), false).toBool();
    _noTyping = _store.value(QStringLiteral("noTyping"), false).toBool();
}

void PrivacySettings::save() {
    _store.setValue(QStringLiteral("invisible"), _invisible);
    _store.setValue(QStringLiteral("noReadReceipts"), _noRead);
    _store.setValue(QStringLiteral("noTyping"), _noTyping);
    _store.sync();
    emit changed();
}

void PrivacySettings::setInvisible(bool v) {
    if (_invisible == v) return;
    _invisible = v;
    save();
}

void PrivacySettings::setNoReadReceipts(bool v) {
    if (_noRead == v) return;
    _noRead = v;
    save();
}

void PrivacySettings::setNoTyping(bool v) {
    if (_noTyping == v) return;
    _noTyping = v;
    save();
}

} // namespace derenguh
