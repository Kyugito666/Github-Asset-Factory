"""
Proxy Converter - Format conversion & deduplication

Supports multiple proxy formats:
- IP:PORT
- IP:PORT:USER:PASS
- USER:PASS@IP:PORT
- http://USER:PASS@IP:PORT

Converts all to standard: http://USER:PASS@IP:PORT
"""

import os
import re
import logging

logger = logging.getLogger(__name__)


def convert_proxylist_to_http(input_file, output_file):
    """
    Convert proxy list ke format HTTP standar.
    
    Supported input formats:
    - user:pass@host:port
    - host:port:user:pass
    - host:port (tanpa auth)
    - http://... (already converted)
    
    Output format:
    - http://user:pass@host:port (with auth)
    - http://host:port (without auth)
    
    Args:
        input_file: Path ke proxylist_downloaded.txt
        output_file: Path ke proxy.txt
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not os.path.exists(input_file):
        logger.error(f"Convert Error: Input '{input_file}' not found.")
        return False
    
    try:
        with open(input_file, "r", encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except IOError as e:
        logger.error(f"Failed read '{input_file}': {e}")
        return False

    if not lines:
        logger.info(f"'{os.path.basename(input_file)}' is empty. Convert skipped.")
        
        # Clean up empty files
        if os.path.exists(output_file):
            try:
                os.remove(output_file)
                logger.info(f"Removed empty output '{os.path.basename(output_file)}'.")
            except OSError as e:
                logger.warning(f"Could not remove '{output_file}': {e}")
        
        try:
            os.remove(input_file)
            logger.info(f"Removed empty input '{os.path.basename(input_file)}'.")
        except OSError as e:
            logger.warning(f"Could not remove '{input_file}': {e}")
        
        return True

    # --- Clean Raw Lines ---
    cleaned_raw = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        
        # Remove http:// or https:// prefix if exists
        if line.startswith("http://"):
            line = line[7:]
        elif line.startswith("https://"):
            line = line[8:]
        
        cleaned_raw.append(line)

    if not cleaned_raw:
        logger.info(f"'{os.path.basename(input_file)}' has no valid content. Convert skipped.")
        try:
            os.remove(input_file)
            logger.info(f"Removed empty/commented '{os.path.basename(input_file)}'.")
        except OSError as e:
            logger.warning(f"Could not remove temporary file '{input_file}': {e}")
        return True

    # --- Convert to HTTP Format ---
    converted = []
    malformed = 0
    count = 0
    total = len(cleaned_raw)
    
    logger.info(f"Converting {total} raw lines...")
    
    # Regex patterns
    host_pat = r"((?:[0-9]{1,3}\.){3}[0-9]{1,3}|(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,})"
    port_pat = r"[0-9]{1,5}"
    
    for p in cleaned_raw:
        count += 1
        result = None
        
        # Format A: user:pass@host:port (already correct, just add http://)
        m_a = re.match(rf"^(?P<up>.+)@(?P<h>{host_pat}):(?P<p>{port_pat})$", p)
        if m_a and m_a.group("p").isdigit() and 1 <= int(m_a.group("p")) <= 65535:
            result = f"http://{p}"
        
        # Format B: host:port:user:pass
        elif p.count(':') == 3 and '@' not in p:
            parts = p.split(':')
            h, pt, u, pw = parts
            
            if re.match(rf"^{host_pat}$", h) and pt.isdigit() and 1 <= int(pt) <= 65535:
                result = f"http://{u}:{pw}@{h}:{pt}"
            else:
                malformed += 1
                logger.debug(f"Skip invalid B: {p}")
        
        # Format C: host:port (no auth)
        elif p.count(':') == 1 and '@' not in p:
            parts = p.split(':')
            h, pt = parts
            
            if re.match(rf"^{host_pat}$", h) and pt.isdigit() and 1 <= int(pt) <= 65535:
                result = f"http://{h}:{pt}"
            else:
                malformed += 1
                logger.debug(f"Skip invalid C: {p}")
        
        # Format D: host:port@user:pass (reversed)
        elif '@' in p and p.count(':') == 2:
            try:
                hp, up = p.split('@', 1)
                h, pt = hp.split(':', 1)
                u, pw = up.split(':', 1)
            except ValueError:
                malformed += 1
                logger.debug(f"Skip malformed D: {p}")
                continue
            
            if re.match(rf"^{host_pat}$", h) and pt.isdigit() and 1 <= int(pt) <= 65535:
                result = f"http://{u}:{pw}@{h}:{pt}"
            else:
                malformed += 1
                logger.debug(f"Skip invalid D: {p}")
        
        if result:
            converted.append(result)
        elif result is None:
            malformed += 1
        
        # Progress log
        if count % 1000 == 0:
            logger.info(f"Convert progress: {count}/{total} lines...")

    if malformed > 0:
        logger.warning(f"Skipped {malformed} lines (format).")
    
    if not converted:
        logger.error("No valid proxies converted.")
        try:
            os.remove(input_file)
            logger.info(f"Removed failed '{os.path.basename(input_file)}'.")
        except OSError as e:
            logger.warning(f"Could not remove '{input_file}': {e}")
        return False

    # --- Save & Deduplicate ---
    try:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        unique = sorted(list(set(converted)))
        dups = len(converted) - len(unique)
        
        if dups > 0:
            logger.info(f"Removed {dups} duplicates.")
        
        with open(output_file, "w", encoding='utf-8') as f:
            f.write('\n'.join(unique) + '\n')
        
        logger.info(f"Converted {len(unique)} unique proxies to '{os.path.basename(output_file)}'.")
        
        # Clean up temp file
        try:
            os.remove(input_file)
            logger.info(f"Removed temp '{os.path.basename(input_file)}'.")
        except OSError as e:
            logger.warning(f"Could not remove '{input_file}': {e}")
        
        return True
        
    except IOError as e:
        logger.error(f"Failed write to '{output_file}': {e}")
        return False


def load_and_deduplicate_proxies(file_path):
    """
    Load proxy list dan remove duplicates.
    
    Args:
        file_path: Path ke proxy.txt
        
    Returns:
        List[str]: Unique proxy list
    """
    if not os.path.exists(file_path):
        logger.warning(f"Dedupe Error: Not found: {file_path}")
        return []
    
    try:
        with open(file_path, "r", encoding='utf-8', errors='ignore') as f:
            proxies = [l.strip() for l in f 
                      if l.strip() and not l.startswith("#")]
    except IOError as e:
        logger.error(f"Failed read {file_path} for dedupe: {e}")
        return []
    
    if not proxies:
        logger.info(f"'{os.path.basename(file_path)}' empty for dedupe.")
        return []

    # Deduplicate
    unique = sorted(list(set(proxies)))
    removed = len(proxies) - len(unique)
    
    if removed > 0:
        logger.info(f"Removed {removed} duplicates from '{os.path.basename(file_path)}'.")
        try:
            with open(file_path, "w", encoding='utf-8') as f:
                f.write('\n'.join(unique) + '\n')
            logger.info(f"Overwrote '{os.path.basename(file_path)}' with {len(unique)} unique.")
        except IOError as e:
            logger.error(f"Failed overwrite {file_path} after dedupe: {e}")
            return unique
    else:
        logger.info(f"No duplicates in '{os.path.basename(file_path)}' ({len(proxies)} unique).")
    
    return unique
