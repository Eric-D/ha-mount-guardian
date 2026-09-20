/* mount-guard-card — artefact de build, ne pas éditer directement. Sources : frontend/src/ */
var ce=Object.defineProperty;var de=Object.getOwnPropertyDescriptor;var C=(r,t,e,s)=>{for(var n=s>1?void 0:s?de(t,e):t,o=r.length-1,i;o>=0;o--)(i=r[o])&&(n=(s?i(t,e,n):i(n))||n);return s&&n&&ce(t,e,n),n};var K=globalThis,Y=K.ShadowRoot&&(K.ShadyCSS===void 0||K.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,it=Symbol(),$t=new WeakMap,P=class{constructor(t,e,s){if(this._$cssResult$=!0,s!==it)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o,e=this.t;if(Y&&t===void 0){let s=e!==void 0&&e.length===1;s&&(t=$t.get(e)),t===void 0&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),s&&$t.set(e,t))}return t}toString(){return this.cssText}},xt=r=>new P(typeof r=="string"?r:r+"",void 0,it),L=(r,...t)=>{let e=r.length===1?r[0]:t.reduce((s,n,o)=>s+(i=>{if(i._$cssResult$===!0)return i.cssText;if(typeof i=="number")return i;throw Error("Value passed to 'css' function must be a 'css' function result: "+i+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(n)+r[o+1],r[0]);return new P(e,r,it)},St=(r,t)=>{if(Y)r.adoptedStyleSheets=t.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let e of t){let s=document.createElement("style"),n=K.litNonce;n!==void 0&&s.setAttribute("nonce",n),s.textContent=e.cssText,r.appendChild(s)}},at=Y?r=>r:r=>r instanceof CSSStyleSheet?(t=>{let e="";for(let s of t.cssRules)e+=s.cssText;return xt(e)})(r):r;var{is:ue,defineProperty:pe,getOwnPropertyDescriptor:he,getOwnPropertyNames:me,getOwnPropertySymbols:fe,getPrototypeOf:ge}=Object,v=globalThis,At=v.trustedTypes,ye=At?At.emptyScript:"",_e=v.reactiveElementPolyfillSupport,U=(r,t)=>r,H={toAttribute(r,t){switch(t){case Boolean:r=r?ye:null;break;case Object:case Array:r=r==null?r:JSON.stringify(r)}return r},fromAttribute(r,t){let e=r;switch(t){case Boolean:e=r!==null;break;case Number:e=r===null?null:Number(r);break;case Object:case Array:try{e=JSON.parse(r)}catch{e=null}}return e}},J=(r,t)=>!ue(r,t),wt={attribute:!0,type:String,converter:H,reflect:!1,useDefault:!1,hasChanged:J};Symbol.metadata??(Symbol.metadata=Symbol("metadata")),v.litPropertyMetadata??(v.litPropertyMetadata=new WeakMap);var y=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??(this.l=[])).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,e=wt){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(t,e),!e.noAccessor){let s=Symbol(),n=this.getPropertyDescriptor(t,s,e);n!==void 0&&pe(this.prototype,t,n)}}static getPropertyDescriptor(t,e,s){let{get:n,set:o}=he(this.prototype,t)??{get(){return this[e]},set(i){this[e]=i}};return{get:n,set(i){let l=n?.call(this);o?.call(this,i),this.requestUpdate(t,l,s)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??wt}static _$Ei(){if(this.hasOwnProperty(U("elementProperties")))return;let t=ge(this);t.finalize(),t.l!==void 0&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(U("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(U("properties"))){let e=this.properties,s=[...me(e),...fe(e)];for(let n of s)this.createProperty(n,e[n])}let t=this[Symbol.metadata];if(t!==null){let e=litPropertyMetadata.get(t);if(e!==void 0)for(let[s,n]of e)this.elementProperties.set(s,n)}this._$Eh=new Map;for(let[e,s]of this.elementProperties){let n=this._$Eu(e,s);n!==void 0&&this._$Eh.set(n,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){let e=[];if(Array.isArray(t)){let s=new Set(t.flat(1/0).reverse());for(let n of s)e.unshift(at(n))}else t!==void 0&&e.push(at(t));return e}static _$Eu(t,e){let s=e.attribute;return s===!1?void 0:typeof s=="string"?s:typeof t=="string"?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??(this._$EO=new Set)).add(t),this.renderRoot!==void 0&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){let t=new Map,e=this.constructor.elementProperties;for(let s of e.keys())this.hasOwnProperty(s)&&(t.set(s,this[s]),delete this[s]);t.size>0&&(this._$Ep=t)}createRenderRoot(){let t=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return St(t,this.constructor.elementStyles),t}connectedCallback(){this.renderRoot??(this.renderRoot=this.createRenderRoot()),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,e,s){this._$AK(t,s)}_$ET(t,e){let s=this.constructor.elementProperties.get(t),n=this.constructor._$Eu(t,s);if(n!==void 0&&s.reflect===!0){let o=(s.converter?.toAttribute!==void 0?s.converter:H).toAttribute(e,s.type);this._$Em=t,o==null?this.removeAttribute(n):this.setAttribute(n,o),this._$Em=null}}_$AK(t,e){let s=this.constructor,n=s._$Eh.get(t);if(n!==void 0&&this._$Em!==n){let o=s.getPropertyOptions(n),i=typeof o.converter=="function"?{fromAttribute:o.converter}:o.converter?.fromAttribute!==void 0?o.converter:H;this._$Em=n;let l=i.fromAttribute(e,o.type);this[n]=l??this._$Ej?.get(n)??l,this._$Em=null}}requestUpdate(t,e,s,n=!1,o){if(t!==void 0){let i=this.constructor;if(n===!1&&(o=this[t]),s??(s=i.getPropertyOptions(t)),!((s.hasChanged??J)(o,e)||s.useDefault&&s.reflect&&o===this._$Ej?.get(t)&&!this.hasAttribute(i._$Eu(t,s))))return;this.C(t,e,s)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(t,e,{useDefault:s,reflect:n,wrapped:o},i){s&&!(this._$Ej??(this._$Ej=new Map)).has(t)&&(this._$Ej.set(t,i??e??this[t]),o!==!0||i!==void 0)||(this._$AL.has(t)||(this.hasUpdated||s||(e=void 0),this._$AL.set(t,e)),n===!0&&this._$Em!==t&&(this._$Eq??(this._$Eq=new Set)).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let t=this.scheduleUpdate();return t!=null&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??(this.renderRoot=this.createRenderRoot()),this._$Ep){for(let[n,o]of this._$Ep)this[n]=o;this._$Ep=void 0}let s=this.constructor.elementProperties;if(s.size>0)for(let[n,o]of s){let{wrapped:i}=o,l=this[n];i!==!0||this._$AL.has(n)||l===void 0||this.C(n,void 0,o,l)}}let t=!1,e=this._$AL;try{t=this.shouldUpdate(e),t?(this.willUpdate(e),this._$EO?.forEach(s=>s.hostUpdate?.()),this.update(e)):this._$EM()}catch(s){throw t=!1,this._$EM(),s}t&&this._$AE(e)}willUpdate(t){}_$AE(t){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&(this._$Eq=this._$Eq.forEach(e=>this._$ET(e,this[e]))),this._$EM()}updated(t){}firstUpdated(t){}};y.elementStyles=[],y.shadowRootOptions={mode:"open"},y[U("elementProperties")]=new Map,y[U("finalized")]=new Map,_e?.({ReactiveElement:y}),(v.reactiveElementVersions??(v.reactiveElementVersions=[])).push("2.1.2");var O=globalThis,Et=r=>r,X=O.trustedTypes,Rt=X?X.createPolicy("lit-html",{createHTML:r=>r}):void 0,Lt="$lit$",b=`lit$${Math.random().toFixed(9).slice(2)}$`,Ut="?"+b,ve=`<${Ut}>`,S=document,D=()=>S.createComment(""),j=r=>r===null||typeof r!="object"&&typeof r!="function",mt=Array.isArray,be=r=>mt(r)||typeof r?.[Symbol.iterator]=="function",lt=`[ 	
\f\r]`,N=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,Ct=/-->/g,Tt=/>/g,$=RegExp(`>|${lt}(?:([^\\s"'>=/]+)(${lt}*=${lt}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),kt=/'/g,Mt=/"/g,Ht=/^(?:script|style|textarea|title)$/i,ft=r=>(t,...e)=>({_$litType$:r,strings:t,values:e}),d=ft(1),Ke=ft(2),Ye=ft(3),A=Symbol.for("lit-noChange"),c=Symbol.for("lit-nothing"),Pt=new WeakMap,x=S.createTreeWalker(S,129);function Nt(r,t){if(!mt(r)||!r.hasOwnProperty("raw"))throw Error("invalid template strings array");return Rt!==void 0?Rt.createHTML(t):t}var $e=(r,t)=>{let e=r.length-1,s=[],n,o=t===2?"<svg>":t===3?"<math>":"",i=N;for(let l=0;l<e;l++){let a=r[l],p,h,u=-1,g=0;for(;g<a.length&&(i.lastIndex=g,h=i.exec(a),h!==null);)g=i.lastIndex,i===N?h[1]==="!--"?i=Ct:h[1]!==void 0?i=Tt:h[2]!==void 0?(Ht.test(h[2])&&(n=RegExp("</"+h[2],"g")),i=$):h[3]!==void 0&&(i=$):i===$?h[0]===">"?(i=n??N,u=-1):h[1]===void 0?u=-2:(u=i.lastIndex-h[2].length,p=h[1],i=h[3]===void 0?$:h[3]==='"'?Mt:kt):i===Mt||i===kt?i=$:i===Ct||i===Tt?i=N:(i=$,n=void 0);let _=i===$&&r[l+1].startsWith("/>")?" ":"";o+=i===N?a+ve:u>=0?(s.push(p),a.slice(0,u)+Lt+a.slice(u)+b+_):a+b+(u===-2?l:_)}return[Nt(r,o+(r[e]||"<?>")+(t===2?"</svg>":t===3?"</math>":"")),s]},I=class r{constructor({strings:t,_$litType$:e},s){let n;this.parts=[];let o=0,i=0,l=t.length-1,a=this.parts,[p,h]=$e(t,e);if(this.el=r.createElement(p,s),x.currentNode=this.el.content,e===2||e===3){let u=this.el.content.firstChild;u.replaceWith(...u.childNodes)}for(;(n=x.nextNode())!==null&&a.length<l;){if(n.nodeType===1){if(n.hasAttributes())for(let u of n.getAttributeNames())if(u.endsWith(Lt)){let g=h[i++],_=n.getAttribute(u).split(b),W=/([.?@])?(.*)/.exec(g);a.push({type:1,index:o,name:W[2],strings:_,ctor:W[1]==="."?dt:W[1]==="?"?ut:W[1]==="@"?pt:k}),n.removeAttribute(u)}else u.startsWith(b)&&(a.push({type:6,index:o}),n.removeAttribute(u));if(Ht.test(n.tagName)){let u=n.textContent.split(b),g=u.length-1;if(g>0){n.textContent=X?X.emptyScript:"";for(let _=0;_<g;_++)n.append(u[_],D()),x.nextNode(),a.push({type:2,index:++o});n.append(u[g],D())}}}else if(n.nodeType===8)if(n.data===Ut)a.push({type:2,index:o});else{let u=-1;for(;(u=n.data.indexOf(b,u+1))!==-1;)a.push({type:7,index:o}),u+=b.length-1}o++}}static createElement(t,e){let s=S.createElement("template");return s.innerHTML=t,s}};function T(r,t,e=r,s){if(t===A)return t;let n=s!==void 0?e._$Co?.[s]:e._$Cl,o=j(t)?void 0:t._$litDirective$;return n?.constructor!==o&&(n?._$AO?.(!1),o===void 0?n=void 0:(n=new o(r),n._$AT(r,e,s)),s!==void 0?(e._$Co??(e._$Co=[]))[s]=n:e._$Cl=n),n!==void 0&&(t=T(r,n._$AS(r,t.values),n,s)),t}var ct=class{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){let{el:{content:e},parts:s}=this._$AD,n=(t?.creationScope??S).importNode(e,!0);x.currentNode=n;let o=x.nextNode(),i=0,l=0,a=s[0];for(;a!==void 0;){if(i===a.index){let p;a.type===2?p=new q(o,o.nextSibling,this,t):a.type===1?p=new a.ctor(o,a.name,a.strings,this,t):a.type===6&&(p=new ht(o,this,t)),this._$AV.push(p),a=s[++l]}i!==a?.index&&(o=x.nextNode(),i++)}return x.currentNode=S,n}p(t){let e=0;for(let s of this._$AV)s!==void 0&&(s.strings!==void 0?(s._$AI(t,s,e),e+=s.strings.length-2):s._$AI(t[e])),e++}},q=class r{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,e,s,n){this.type=2,this._$AH=c,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=s,this.options=n,this._$Cv=n?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode,e=this._$AM;return e!==void 0&&t?.nodeType===11&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=T(this,t,e),j(t)?t===c||t==null||t===""?(this._$AH!==c&&this._$AR(),this._$AH=c):t!==this._$AH&&t!==A&&this._(t):t._$litType$!==void 0?this.$(t):t.nodeType!==void 0?this.T(t):be(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==c&&j(this._$AH)?this._$AA.nextSibling.data=t:this.T(S.createTextNode(t)),this._$AH=t}$(t){let{values:e,_$litType$:s}=t,n=typeof s=="number"?this._$AC(t):(s.el===void 0&&(s.el=I.createElement(Nt(s.h,s.h[0]),this.options)),s);if(this._$AH?._$AD===n)this._$AH.p(e);else{let o=new ct(n,this),i=o.u(this.options);o.p(e),this.T(i),this._$AH=o}}_$AC(t){let e=Pt.get(t.strings);return e===void 0&&Pt.set(t.strings,e=new I(t)),e}k(t){mt(this._$AH)||(this._$AH=[],this._$AR());let e=this._$AH,s,n=0;for(let o of t)n===e.length?e.push(s=new r(this.O(D()),this.O(D()),this,this.options)):s=e[n],s._$AI(o),n++;n<e.length&&(this._$AR(s&&s._$AB.nextSibling,n),e.length=n)}_$AR(t=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);t!==this._$AB;){let s=Et(t).nextSibling;Et(t).remove(),t=s}}setConnected(t){this._$AM===void 0&&(this._$Cv=t,this._$AP?.(t))}},k=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,e,s,n,o){this.type=1,this._$AH=c,this._$AN=void 0,this.element=t,this.name=e,this._$AM=n,this.options=o,s.length>2||s[0]!==""||s[1]!==""?(this._$AH=Array(s.length-1).fill(new String),this.strings=s):this._$AH=c}_$AI(t,e=this,s,n){let o=this.strings,i=!1;if(o===void 0)t=T(this,t,e,0),i=!j(t)||t!==this._$AH&&t!==A,i&&(this._$AH=t);else{let l=t,a,p;for(t=o[0],a=0;a<o.length-1;a++)p=T(this,l[s+a],e,a),p===A&&(p=this._$AH[a]),i||(i=!j(p)||p!==this._$AH[a]),p===c?t=c:t!==c&&(t+=(p??"")+o[a+1]),this._$AH[a]=p}i&&!n&&this.j(t)}j(t){t===c?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}},dt=class extends k{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===c?void 0:t}},ut=class extends k{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==c)}},pt=class extends k{constructor(t,e,s,n,o){super(t,e,s,n,o),this.type=5}_$AI(t,e=this){if((t=T(this,t,e,0)??c)===A)return;let s=this._$AH,n=t===c&&s!==c||t.capture!==s.capture||t.once!==s.once||t.passive!==s.passive,o=t!==c&&(s===c||n);n&&this.element.removeEventListener(this.name,this,s),o&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}},ht=class{constructor(t,e,s){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=s}get _$AU(){return this._$AM._$AU}_$AI(t){T(this,t)}};var xe=O.litHtmlPolyfillSupport;xe?.(I,q),(O.litHtmlVersions??(O.litHtmlVersions=[])).push("3.3.3");var Ot=(r,t,e)=>{let s=e?.renderBefore??t,n=s._$litPart$;if(n===void 0){let o=e?.renderBefore??null;s._$litPart$=n=new q(t.insertBefore(D(),o),o,void 0,e??{})}return n._$AI(r),n};var z=globalThis,f=class extends y{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){var e;let t=super.createRenderRoot();return(e=this.renderOptions).renderBefore??(e.renderBefore=t.firstChild),t}update(t){let e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=Ot(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return A}};f._$litElement$=!0,f.finalized=!0,z.litElementHydrateSupport?.({LitElement:f});var Se=z.litElementPolyfillSupport;Se?.({LitElement:f});(z.litElementVersions??(z.litElementVersions=[])).push("4.2.2");var Ae={attribute:!0,type:String,converter:H,reflect:!1,hasChanged:J},we=(r=Ae,t,e)=>{let{kind:s,metadata:n}=e,o=globalThis.litPropertyMetadata.get(n);if(o===void 0&&globalThis.litPropertyMetadata.set(n,o=new Map),s==="setter"&&((r=Object.create(r)).wrapped=!0),o.set(e.name,r),s==="accessor"){let{name:i}=e;return{set(l){let a=t.get.call(this);t.set.call(this,l),this.requestUpdate(i,a,r,!0,l)},init(l){return l!==void 0&&this.C(i,void 0,r,l),l}}}if(s==="setter"){let{name:i}=e;return function(l){let a=this[i];t.call(this,l),this.requestUpdate(i,a,r,!0,l)}}throw Error("Unsupported decorator location: "+s)};function Q(r){return(t,e)=>typeof e=="object"?we(r,t,e):((s,n,o)=>{let i=n.hasOwnProperty(o);return n.constructor.createProperty(o,s),i?Object.getOwnPropertyDescriptor(n,o):void 0})(r,t,e)}function B(r){return Q({...r,state:!0,attribute:!1})}var Ee="0.1.0-alpha.1";function Dt(){console.info(`%c MOUNT-GUARD-CARD %c ${Ee} IS INSTALLED `,"color: white; background: #1565c0; font-weight: bold;","color: #1565c0; background: #bbdefb; font-weight: bold;")}function m(r,t,e,...s){let n=`%c MOUNT-GUARD-CARD %c [${t}]`,o=["color: white; background: #1565c0; font-weight: bold;","color: #1565c0; font-weight: bold;"];console[r](n+" "+e,...o,...s)}var jt=10,Re=2e3,Ce=15e3,tt=class{constructor(t,e){this.cardName=t;this.fire=e;this.timer=null;this.count=0}schedule(){if(this.timer||(this.count++,this.count>jt))return;let t=Math.min(Re*this.count,Ce);m("info",this.cardName,"Retry %d dans %dms\u2026",this.count,t),this.timer=setTimeout(()=>{this.timer=null,this.fire()},t)}get exhausted(){return this.count>jt}reset(){this.count=0,this.cancel()}cancel(){this.timer&&(clearTimeout(this.timer),this.timer=null)}};var Te={repairing:3,pending:2,degraded:1,ok:0};function It(r){return Te[r.state]??0}function gt(r,t){let e=t.mounts,s=t.show_ok!==!1;return r.filter(n=>!e||e.length===0||e.includes(n.mount)).filter(n=>s||n.state!=="ok").slice().sort((n,o)=>It(o)-It(n)||n.mount.localeCompare(o.mount))}function qt(r,t){return r.length===0?"none-configured":gt(r,t).length===0?"all-healthy":null}var ke="addon_mount_guard/subscribe",et=class{constructor(t,e){this.onRemediation=t;this.onStateChange=e;this.unsubscribe=null;this.generation=0;this.lost=!1}get active(){return this.unsubscribe!==null}async connect(t){if(this.unsubscribe||!t?.connection?.subscribeMessage)return;let e=++this.generation;try{let s=await t.connection.subscribeMessage(n=>{n?.remediation&&this.onRemediation(n.remediation)},{type:ke});if(e!==this.generation){s();return}this.unsubscribe=s,this.lost=!1}catch(s){this.lost=this.lost||!1,m("warn","feed","souscription impossible, repli sur le capteur : %o",s)}this.onStateChange()}disconnect(){if(this.generation++,!!this.unsubscribe){try{this.unsubscribe()}catch(t){m("warn","feed","d\xE9sabonnement en \xE9chec : %o",t)}this.unsubscribe=null}}markLost(){this.unsubscribe=null,this.lost=!0,this.onStateChange()}};function zt(r,t){let e=new Map;for(let s of r)e.set(s.mount,s);for(let[s,n]of t)e.set(s,n);return[...e.values()]}function Bt({title:r,count:t}){return d`
    <div class="header">
      <div class="title">${r}</div>
      <div class="count">
        ${t===0?"aucune rem\xE9diation":`${t} rem\xE9diation${t>1?"s":""} en cours`}
      </div>
    </div>
  `}function Gt(r){return r?d`
    <div class="notice" role="status">
      <ha-icon icon="mdi:alert-outline"></ha-icon><span>${r}</span>
    </div>
  `:c}function G(r){return d`<ha-card><div class="loader">${r}</div></ha-card>`}function Vt(r){return d`
    <div class="empty">
      ${r==="none-configured"?"Aucun add-on surveill\xE9. Ajoutez-en un depuis la fiche de l'int\xE9gration.":"Tous les montages sont op\xE9rationnels."}
    </div>
  `}var Ft=["o","ko","Mo","Go","To"];function yt(r){if(!Number.isFinite(r)||r<0)return"\u2014";if(r<1e3)return`${Math.round(r)} o`;let t=r,e=0;for(;t>=1e3&&e<Ft.length-1;)t/=1e3,e++;return`${t<10?t.toFixed(1):Math.round(t)} ${Ft[e]}`}function _t(r){if(!Number.isFinite(r)||r<0)return"\u2014";let t=Math.floor(r);if(t<60)return`${t} s`;let e=Math.floor(t/60);return e<60?`${e} min ${String(t%60).padStart(2,"0")} s`:`${Math.floor(e/60)} h ${String(e%60).padStart(2,"0")}`}function vt(r){if(!Number.isFinite(r))return"\u2014";let t=Math.max(0,Math.floor(r)),e=Math.floor(t/60);return`${String(e).padStart(2,"0")}:${String(t%60).padStart(2,"0")}`}function rt(r,t=Date.now()){if(!r)return null;let e=Date.parse(r);return Number.isNaN(e)?null:(t-e)/1e3}function bt(r,t=Date.now()){let e=rt(r,t);return e===null?null:-e}function Wt(r,t=48){return r?r.length<=t?r:`\u2026${r.slice(r.length-t+1)}`:""}function Kt(r){let{files_done:t,files_total:e}=r,{bytes_done:s,bytes_total:n}=r,o=null;return n>0?o=s/n:e>0&&(o=t/e),{ratio:o===null?null:Math.min(Math.max(o,0),1),filesDone:t,filesTotal:e,bytesDone:s,bytesTotal:n}}function st(r){return r===null?"":`${Math.round(r*100)} %`}var Yt={local_fallback:["stopping","stashing","reloading","restoring","starting"],stop_only:["stopping","reloading","starting"]},M={stopping:"Arr\xEAt",stashing:"Mise de c\xF4t\xE9",reloading:"Rechargement",restoring:"Rapatriement",rolling_back:"Retour arri\xE8re",starting:"Relance"};function Jt(r){let t=Yt[r.mode]??Yt.local_fallback,e=r.step==="rolling_back",s=r.step_index;return t.map((n,o)=>{let i=o+1,l="todo";return i<s?l="done":i===s&&(l=e?"failed":"active"),{index:i,step:n,label:M[e&&i===s?"rolling_back":n],state:l}})}function Xt(r){return r.state==="repairing"}function Qt(r){return r.state==="degraded"||r.state==="pending"}var Me={ok:"normal",degraded:"d\xE9grad\xE9",pending:"r\xE9paration due",repairing:"r\xE9paration"};function Zt(r){return Me[r]??r}function te(r){return r.length===0?c:d`
    <details class="history">
      <summary>Historique (${r.length})</summary>
      <table>
        ${r.map(t=>d`
            <tr>
              <td class="at">${new Date(t.at).toLocaleString()}</td>
              <td>${Zt(t.from)} → ${Zt(t.to)}</td>
              <td>${t.step?M[t.step]??t.step:""}</td>
              <td>${t.error??""}</td>
            </tr>
          `)}
      </table>
    </details>
  `}function ee(r){return d`
    <div class="stepper" role="list">
      ${r.map(t=>d`
          <div class="step ${t.state}" role="listitem" aria-current=${t.state==="active"}>
            <div class="bar"></div>
            <div class="label" title=${t.label}>${t.label}</div>
          </div>
        `)}
    </div>
  `}function re({progress:r,currentFile:t}){let e=r.ratio===null?0:r.ratio*100;return d`
    <div class="progress">
      <div
        class="track"
        role="progressbar"
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow=${Math.round(e)}
      >
        <div class="fill" style="width: ${e}%"></div>
      </div>
      <div class="numbers">
        <span
          >${r.filesDone} / ${r.filesTotal} fichiers
          ${r.ratio===null?"":`(${st(r.ratio)})`}</span
        >
        <span>${yt(r.bytesDone)} / ${yt(r.bytesTotal)}</span>
      </div>
      ${t?d`<div class="current" title=${t}>${Wt(t)}</div>`:""}
    </div>
  `}var se={ok:"var(--success-color)",degraded:"var(--warning-color)",pending:"var(--primary-color)",repairing:"var(--primary-color)"},V={ok:"Normal",degraded:"D\xE9grad\xE9",pending:"R\xE9paration en attente",repairing:"R\xE9paration"},Pe={started:"d\xE9marr\xE9",stopped:"arr\xEAt\xE9",held:"maintenu arr\xEAt\xE9",unknown:"\xE9tat inconnu"};function ne(r){return r.addons.length===0?"":r.addons.map(t=>`${t.name} \u2014 ${Pe[t.state]??t.state}`).join(" \xB7 ")}function oe({remediation:r,now:t,showHistory:e,compact:s,onRepair:n,onCancel:o}){let i=r.state==="repairing",l=Jt(r),a=Kt(r);return s?d`
      <div class="mount compact" data-mount=${r.mount}>
        <div class="row">
          <span class="dot" style="--dot-color: ${se[r.state]}"></span>
          <span class="name">${r.mount}</span>
          <span class="summary">${He(r,a.ratio,t)}</span>
        </div>
      </div>
    `:d`
    <div class="mount" data-mount=${r.mount}>
      <div class="row">
        <span class="dot" style="--dot-color: ${se[r.state]}"></span>
        <span class="name">${r.mount}</span>
        <span class="path">${r.path}</span>
      </div>

      ${ne(r)?d`<div class="addons">${ne(r)}</div>`:""}

      ${i?d`
            ${ee(l)}
            ${r.step==="restoring"||r.step==="rolling_back"?re({progress:a,currentFile:r.current_file}):c}
            <div class="meta">${Le(r,t)}</div>
          `:d`<div class="meta">${Ue(r,t)}</div>`}

      ${r.last_error?d`<div class="error">${r.last_error}</div>`:""}

      <div class="actions">
        <mwc-button
          class="repair"
          ?disabled=${!Qt(r)}
          @click=${()=>n(r.mount)}
          >Réparer maintenant</mwc-button
        >
        <mwc-button
          class="cancel"
          ?disabled=${!Xt(r)}
          @click=${()=>o(r.mount)}
          >Annuler</mwc-button
        >
      </div>

      ${e?te(r.history):c}
    </div>
  `}function Le(r,t){let e=rt(r.started_at,t),s=r.step?M[r.step]:"",n=`\xE9tape ${r.step_index} sur ${r.step_count}`;return e===null?`${s} \u2014 ${n}`:`${s} \u2014 ${n} \xB7 depuis ${_t(e)}`}function Ue(r,t){if(r.state==="ok")return V.ok;let e=bt(r.next_retry_at,t),s=rt(r.last_incident_at,t),n=[V[r.state]];return s!==null&&n.push(`depuis ${_t(s)}`),e!==null&&n.push(`nouvelle tentative dans ${vt(e)}`),n.join(" \xB7 ")}function He(r,t,e){if(r.state==="repairing"){let n=r.step?M[r.step]:"",o=st(t);return o?`${n} \xB7 ${o}`:n}if(r.state==="ok")return V.ok;let s=bt(r.next_retry_at,e);return s===null?V[r.state]:`${V[r.state]} \xB7 ${vt(s)}`}var ie=L`
  :host {
    display: block;
  }

  ha-card {
    padding: 0;
    overflow: hidden;
  }

  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 16px 16px 8px;
  }

  .title {
    font-size: 1.15rem;
    font-weight: 500;
    color: var(--primary-text-color);
  }

  .count {
    font-size: 0.85rem;
    color: var(--secondary-text-color);
  }

  .notice {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 0 16px 12px;
    padding: 8px 12px;
    border-radius: 8px;
    background: var(--secondary-background-color);
    color: var(--primary-text-color);
    font-size: 0.85rem;
  }

  .notice ha-icon {
    --mdc-icon-size: 18px;
    color: var(--warning-color);
    flex: 0 0 auto;
  }

  .empty {
    padding: 8px 16px 20px;
    color: var(--secondary-text-color);
  }

  .mount {
    padding: 12px 16px;
    border-top: 1px solid var(--divider-color);
  }

  .mount:first-of-type {
    border-top: none;
  }

  .row {
    display: flex;
    align-items: baseline;
    gap: 8px;
  }

  /* La pastille ne porte jamais de texte : sa couleur est un renfort, et le
     libellé à côté porte l'information. Une pastille seule serait illisible
     pour un daltonien, et le contraste ne distingue pas trois états. */
  .dot {
    flex: 0 0 auto;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--dot-color, var(--disabled-text-color));
  }

  .name {
    font-weight: 500;
    color: var(--primary-text-color);
  }

  .path {
    margin-left: auto;
    font-size: 0.8rem;
    color: var(--secondary-text-color);
    font-family: var(--code-font-family, monospace);
  }

  .addons,
  .meta {
    margin-top: 4px;
    font-size: 0.85rem;
    color: var(--secondary-text-color);
  }

  .error {
    margin-top: 6px;
    font-size: 0.85rem;
    color: var(--error-color);
  }

  .actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    margin-top: 10px;
  }

  mwc-button[disabled] {
    opacity: 0.5;
  }

  .history {
    margin-top: 8px;
    font-size: 0.8rem;
    color: var(--secondary-text-color);
  }

  .history summary {
    cursor: pointer;
    user-select: none;
  }

  .history table {
    margin-top: 6px;
    border-collapse: collapse;
    width: 100%;
  }

  .history td {
    padding: 2px 8px 2px 0;
    vertical-align: top;
  }

  .history .at {
    white-space: nowrap;
    font-family: var(--code-font-family, monospace);
  }

  .compact .row {
    align-items: center;
  }

  .compact .summary {
    color: var(--secondary-text-color);
    font-size: 0.85rem;
    margin-left: auto;
  }

  .loader {
    padding: 24px 16px;
    color: var(--secondary-text-color);
  }
`;var ae=L`
  .stepper {
    display: flex;
    align-items: flex-start;
    gap: 4px;
    margin: 10px 0 6px;
  }

  .step {
    flex: 1 1 0;
    min-width: 0;
    text-align: center;
  }

  .bar {
    height: 4px;
    border-radius: 2px;
    background: var(--divider-color);
  }

  .step.done .bar {
    background: var(--success-color);
  }

  .step.active .bar {
    background: var(--primary-color);
  }

  .step.failed .bar {
    background: var(--error-color);
  }

  .step .label {
    margin-top: 4px;
    font-size: 0.7rem;
    color: var(--secondary-text-color);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* L'étape en cours est la seule en couleur de texte pleine : sur une carte
     de cinq cases, mettre tout en évidence revient à ne rien mettre en
     évidence. */
  .step.active .label {
    color: var(--primary-text-color);
    font-weight: 500;
  }

  .step.failed .label {
    color: var(--error-color);
    font-weight: 500;
  }

  .progress {
    margin-top: 8px;
  }

  .track {
    height: 6px;
    border-radius: 3px;
    background: var(--divider-color);
    overflow: hidden;
  }

  .fill {
    height: 100%;
    background: var(--primary-color);
    transition: width 0.3s ease;
  }

  .numbers {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    margin-top: 4px;
    font-size: 0.8rem;
    color: var(--secondary-text-color);
  }

  .current {
    margin-top: 2px;
    font-size: 0.78rem;
    color: var(--secondary-text-color);
    font-family: var(--code-font-family, monospace);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    direction: rtl;
    text-align: left;
  }
`;var w="sensor.mount_guard_remediations";var Ne={entity:"Entit\xE9 (capteur des rem\xE9diations)",title:"Titre personnalis\xE9",mounts:"Montages affich\xE9s (vide = tous)",show_ok:"Afficher les montages sains",show_history:"Afficher l'historique",compact:"Mode compact (tableau de bord mural)"},Oe=[{name:"entity",required:!0,selector:{entity:{domain:"sensor",integration:"addon_mount_guard"}}},{name:"title",selector:{text:{}}},{name:"mounts",selector:{text:{multiple:!0}}},{name:"show_ok",selector:{boolean:{}}},{name:"show_history",selector:{boolean:{}}},{name:"compact",selector:{boolean:{}}}],De=r=>Ne[r.name]??r.name,F=class extends f{constructor(){super(...arguments);this._config={entity:w}}setConfig(e){this._config=e??{entity:w}}createRenderRoot(){return this}render(){return this.hass?d`
      <ha-form
        .hass=${this.hass}
        .data=${this._config}
        .schema=${Oe}
        .computeLabel=${De}
        @value-changed=${this._valueChanged}
      ></ha-form>
    `:d``}_valueChanged(e){let s={...e.detail.value};for(let n of Object.keys(s)){if(n==="entity"){typeof s[n]!="string"&&(s[n]="");continue}let o=s[n];(o===""||o===void 0||o===null)&&delete s[n],Array.isArray(o)&&o.length===0&&delete s[n]}this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:s},bubbles:!0,composed:!0}))}};C([Q({attribute:!1})],F.prototype,"hass",2),C([B()],F.prototype,"_config",2);customElements.get("mount-guard-card-editor")||customElements.define("mount-guard-card-editor",F);var je=1e3,E=class E extends f{constructor(){super(...arguments);this._now=Date.now();this._id=++E._instances;this._live=new Map;this._retry=new tt("card",()=>this.requestUpdate());this._feed=new et(e=>{this._live.set(e.mount,e),this.requestUpdate()},()=>this.requestUpdate());this._tick=null;this._firstUpdateLogged=!1}static getConfigElement(){return document.createElement("mount-guard-card-editor")}static getStubConfig(){return{entity:w}}set hass(e){this._hass=e,this._syncEntityState(),this._feed.connect(e)}get hass(){return this._hass}setConfig(e){if(!e||typeof e!="object")throw m("error","card","setConfig rejet\xE9, config non-objet : %o",e),new Error("Configuration manquante ou invalide");let s=w;typeof e.entity=="string"&&e.entity!==""?s=e.entity:e.entity!==void 0&&e.entity!==null&&e.entity!==""&&m("error","card","'entity' doit \xEAtre une cha\xEEne, re\xE7u %o \u2014 repli sur %s",e.entity,w),this._config={...e,entity:s,mounts:Array.isArray(e.mounts)?e.mounts.map(String):void 0},this._syncEntityState(),m("info","card","#%d setConfig accept\xE9 (entity=%s)",this._id,s)}getCardSize(){return 1+this._remediations().length*2}getGridOptions(){return{columns:12,min_columns:6,rows:"auto",min_rows:2}}connectedCallback(){super.connectedCallback(),this._retry.reset(),this._tick=setInterval(()=>{this._now=Date.now()},je),this._feed.connect(this._hass)}disconnectedCallback(){this._retry.cancel(),this._tick&&(clearInterval(this._tick),this._tick=null),this._feed.disconnect(),super.disconnectedCallback()}shouldUpdate(e){return e.has("_config")||e.has("_now")?!0:this._entityState!==this._renderedEntityState}render(){return this._render()}updated(){this._renderedEntityState=this._entityState,this._firstUpdateLogged||(this._firstUpdateLogged=!0,m("info","card","#%d premier rendu effectu\xE9 \xE0 t=%dms",this._id,Math.round(performance.now()))),this.dispatchEvent(new CustomEvent("mount-guard-card-update",{bubbles:!0,composed:!0}))}_syncEntityState(){let e=this._config?.entity;this._entityState=e?this._hass?.states[e]:void 0}_remediations(){let e=this._entityState?.attributes??{},s=Array.isArray(e.remediations)?e.remediations:[];return zt(s,this._live)}_call(e,s){this._hass?.callService("addon_mount_guard",e,{mount:s}).catch(n=>m("error","card","%s(%s) : %o",e,s,n))}_render(){let e=this._config;if(!e)return G("Carte en attente de configuration\u2026");if(!this._hass?.states)return this._retry.schedule(),this._lastTemplate&&!this._retry.exhausted?this._lastTemplate:G("En attente de Home Assistant\u2026");if(!this._entityState)return this._retry.schedule(),this._lastTemplate&&!this._retry.exhausted?this._lastTemplate:G(`Entit\xE9 ${e.entity} introuvable.`);if(this._entityState.state==="unavailable")return this._retry.schedule(),this._lastTemplate&&!this._retry.exhausted?this._lastTemplate:G(`Entit\xE9 ${e.entity} indisponible.`);this._retry.reset();let n=this._remediations(),o=gt(n,e),i=qt(n,e),l=n.filter(p=>p.state==="repairing"||p.state==="pending").length,a=d`
      <ha-card>
        ${Bt({title:e.title??"Montages surveill\xE9s",count:l})}
        ${Gt(this._noticeMessage())}
        ${i?Vt(i):o.map(p=>oe({remediation:p,now:this._now,showHistory:e.show_history===!0,compact:e.compact===!0,onRepair:h=>this._call("repair",h),onCancel:h=>this._call("cancel",h)}))}
      </ha-card>
    `;return this._lastTemplate=a,a}_noticeMessage(){return this._feed.lost&&!this._feed.active?"Connexion temps r\xE9el perdue \u2014 donn\xE9es du dernier relev\xE9.":null}};E.styles=[ie,ae],E._instances=0,C([B()],E.prototype,"_config",2),C([B()],E.prototype,"_now",2);var nt=E;window.loadCardHelpers?.().catch(r=>{m("warn","card","loadCardHelpers() a \xE9chou\xE9 : %o",r)});var R="mount-guard-card",Ie=5,le=0;function qe(){if(customElements.get(R)||le>=Ie)return!1;le++;try{return customElements.define(R,class extends nt{}),m("warn","card","r\xE9-enregistr\xE9 \xE0 t=%dms : le registre d'\xE9l\xE9ments personnalis\xE9s avait \xE9t\xE9 remplac\xE9 depuis le premier enregistrement",Math.round(performance.now())),!0}catch(r){return m("error","card","r\xE9-enregistrement impossible : %o",r),!1}}customElements.get(R)?m("info","card","module d\xE9j\xE0 enregistr\xE9, ce chargement est ignor\xE9"):(customElements.define(R,nt),m("info","card","\xE9l\xE9ment enregistr\xE9 \xE0 t=%dms",Math.round(performance.now())));function ze(){let r=0,t=e=>{if(e.localName==="hui-error-card"){let s=e;((s._config??s.config)?.message??"").includes(R)&&(e.dispatchEvent(new CustomEvent("ll-rebuild",{bubbles:!0,composed:!0})),r++);return}for(let s of[...e.shadowRoot?.children??[],...e.children])t(s)};return document.body&&t(document.body),r}for(let r of[0,50,150,400,1e3,2e3,4e3])window.setTimeout(()=>{try{qe();let t=ze();t>0&&m("warn","card","%d carte(s) d'erreur reconstruite(s) apr\xE8s %dms",t,r)}catch(t){m("error","card","r\xE9paration des cartes d'erreur impossible : %o",t)}},r);var ot=window;ot.customCards=ot.customCards??[];ot.customCards.some(r=>r.type===R)||ot.customCards.push({type:R,name:"Add-on Mount Guard",description:"Suit les rem\xE9diations des stockages r\xE9seau tomb\xE9s sous les add-ons"});Dt();export{nt as MountGuardCard};
